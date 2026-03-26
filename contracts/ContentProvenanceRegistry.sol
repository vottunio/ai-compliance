// SPDX-License-Identifier: MIT
pragma solidity ^0.8.25;

/// @title ContentProvenanceRegistry
/// @notice EU AI Act Article 50 compliant provenance registry
/// @dev Designed for Base L2 deployment (low gas, high auditability)
contract ContentProvenanceRegistry {

    // ------------------------------------------------------------
    // ENUMS
    // ------------------------------------------------------------

    /// @notice Regulatory classification of AI-generated content
    enum GenerationType {
        FullyGenerated,   // 0
        AIAssisted,       // 1
        Manipulated,      // 2
        Deepfake          // 3
    }

    // ------------------------------------------------------------
    // STRUCTS
    // ------------------------------------------------------------

    /// @notice On-chain minimal provenance record.
    /// @dev Maps to POST /v1/certify (CertifyRequest) on-chain fields:
    ///   content_hash -> contentHash, creator_hash/creator_id -> creatorHash,
    ///   parent_certificate_id -> parentCertificateId, generation_type -> generationType,
    ///   model_id -> modelId, prompt_hash -> promptHash,
    ///   deployer_disclosure_applied -> deployerDisclosureApplied, metadata_cid -> metadataCID.
    ///   API-only (not on-chain): content_type, creator_id, metadata.
    struct Certificate {
        bytes32 certificateId;          // certId (e.g. from vtn_uuid)
        bytes32 contentHash;            // SHA-256 of watermarked content
        bytes4 watermarkPayload;        // Phase 3: payload for findByPayload; 0 = no watermark
        bytes32 creatorHash;            // hashed creator identifier (CertifyRequest.creator_hash or derived from creator_id)
        bytes32 parentCertificateId;    // modification chain link (CertifyRequest.parent_certificate_id)
        GenerationType generationType;  // regulatory classification (CertifyRequest.generation_type 0-3)
        bytes32 promptHash;             // optional prompt hash (CertifyRequest.prompt_hash)
        address providerAddress;        // system provider
        address certifierAddress;       // authorized certifier wallet
        bool deployerDisclosureApplied; // Article 50(4) (CertifyRequest.deployer_disclosure_applied)
        uint256 timestamp;              // block.timestamp
        string modelId;                 // AI system identifier (CertifyRequest.model_id)
        string metadataCID;             // IPFS CID (CertifyRequest.metadata_cid)
    }

    /// @notice One item for batch certification. Field-for-field matches CertifyRequest on-chain fields.
    /// @dev POST /v1/batch (BatchCertifyRequest) sends items[]; each element maps to BatchItem here.
    struct BatchItem {
        bytes32 certId;                 // Phase 3: certificate ID per item
        bytes32 contentHash;            // SHA-256 of (watermarked) content
        bytes4 watermarkPayload;        // Phase 3: 0 = no watermark
        bytes32 creatorHash;
        bytes32 parentCertificateId;
        GenerationType generationType;
        string modelId;
        bytes32 promptHash;
        bool deployerDisclosureApplied;
        string metadataCID;
    }

    // ------------------------------------------------------------
    // STORAGE
    // ------------------------------------------------------------

    address public owner;

    mapping(address => bool) public authorizedCertifiers;
    mapping(bytes32 => Certificate) private certificates;
    mapping(bytes32 => bool) public certified;
    /// @dev Phase 3: index for findByPayload(watermarkPayload) -> certIds[]
    mapping(bytes4 => bytes32[]) private payloadIndex;

    uint256 public certificateCount;

    // ------------------------------------------------------------
    // EVENTS (Compliance Logging)
    // ------------------------------------------------------------

    event ContentCertified(
        bytes32 indexed certificateId,
        bytes32 indexed contentHash,
        GenerationType generationType,
        address indexed certifier,
        uint256 timestamp
    );

    event BatchCertified(
        address indexed certifier,
        uint256 count,
        uint256 timestamp
    );

    event VerificationPerformed(
        bytes32 indexed contentHash,
        bool success,
        uint256 timestamp
    );

    event CertifierAdded(address indexed account);
    event CertifierRemoved(address indexed account);

    // ------------------------------------------------------------
    // MODIFIERS
    // ------------------------------------------------------------

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    modifier onlyCertifier() {
        require(
            msg.sender == owner || authorizedCertifiers[msg.sender],
            "Not authorized certifier"
        );
        _;
    }

    // ------------------------------------------------------------
    // CONSTRUCTOR
    // ------------------------------------------------------------

    constructor() {
        owner = msg.sender;
        authorizedCertifiers[msg.sender] = true;
        emit CertifierAdded(msg.sender);
    }

    // ------------------------------------------------------------
    // ACCESS CONTROL
    // ------------------------------------------------------------

    function addCertifier(address account) external onlyOwner {
        require(account != address(0), "Invalid address");
        require(!authorizedCertifiers[account], "Already certifier");
        authorizedCertifiers[account] = true;
        emit CertifierAdded(account);
    }

    function removeCertifier(address account) external onlyOwner {
        require(authorizedCertifiers[account], "Not certifier");
        authorizedCertifiers[account] = false;
        emit CertifierRemoved(account);
    }

    // ------------------------------------------------------------
    // SINGLE CERTIFICATION (Phase 3: by certId + Certificate with watermarkPayload)
    // ------------------------------------------------------------

    /// @param certId Public certificate ID (e.g. bytes32 from vtn_uuid)
    /// @param cert Certificate data; contentHash = hash of watermarked content; watermarkPayload = bytes4 or 0
    function certify(
        bytes32 certId,
        Certificate calldata cert
    ) external onlyCertifier returns (bytes32) {
        require(certId != bytes32(0), "Invalid certId");
        require(!certified[certId], "Already certified");
        require(cert.contentHash != bytes32(0), "Invalid contentHash");

        if (cert.parentCertificateId != bytes32(0)) {
            require(certified[cert.parentCertificateId], "Parent not found");
        }

        certified[certId] = true;
        certificates[certId] = Certificate({
            certificateId: certId,
            contentHash: cert.contentHash,
            watermarkPayload: cert.watermarkPayload,
            creatorHash: cert.creatorHash,
            parentCertificateId: cert.parentCertificateId,
            generationType: cert.generationType,
            promptHash: cert.promptHash,
            providerAddress: owner,
            certifierAddress: msg.sender,
            deployerDisclosureApplied: cert.deployerDisclosureApplied,
            timestamp: block.timestamp,
            modelId: cert.modelId,
            metadataCID: cert.metadataCID
        });

        if (cert.watermarkPayload != bytes4(0)) {
            payloadIndex[cert.watermarkPayload].push(certId);
        }

        certificateCount++;

        emit ContentCertified(
            certId,
            cert.contentHash,
            cert.generationType,
            msg.sender,
            block.timestamp
        );
        return certId;
    }

    // ------------------------------------------------------------
    // BATCH CERTIFICATION (matches POST /v1/batch BatchCertifyRequest.items)
    // ------------------------------------------------------------

    /// @param items Array of BatchItem; each item maps to one CertifyRequest in BatchCertifyRequest.items (max 100)
    function certifyBatch(
        BatchItem[] calldata items
    ) external onlyCertifier returns (bytes32[] memory certificateIds) {

        uint256 length = items.length;
        require(length > 0, "Empty batch");

        certificateIds = new bytes32[](length);

        for (uint256 i = 0; i < length; i++) {
            BatchItem calldata item = items[i];

            require(item.certId != bytes32(0), "Invalid certId");
            require(item.contentHash != bytes32(0), "Invalid hash");
            require(!certified[item.certId], "Already certified");

            if (item.parentCertificateId != bytes32(0)) {
                require(
                    certified[item.parentCertificateId],
                    "Parent not found"
                );
            }

            certified[item.certId] = true;

            certificates[item.certId] = Certificate({
                certificateId: item.certId,
                contentHash: item.contentHash,
                watermarkPayload: item.watermarkPayload,
                creatorHash: item.creatorHash,
                parentCertificateId: item.parentCertificateId,
                generationType: item.generationType,
                promptHash: item.promptHash,
                providerAddress: owner,
                certifierAddress: msg.sender,
                deployerDisclosureApplied: item.deployerDisclosureApplied,
                timestamp: block.timestamp,
                modelId: item.modelId,
                metadataCID: item.metadataCID
            });

            if (item.watermarkPayload != bytes4(0)) {
                payloadIndex[item.watermarkPayload].push(item.certId);
            }

            certificateIds[i] = item.certId;

            emit ContentCertified(
                item.certId,
                item.contentHash,
                item.generationType,
                msg.sender,
                block.timestamp
            );
        }

        certificateCount += length;

        emit BatchCertified(msg.sender, length, block.timestamp);

        return certificateIds;
    }

    // ------------------------------------------------------------
    // PUBLIC VERIFICATION (NO AUTH REQUIRED) — Phase 3: by certId
    // ------------------------------------------------------------

    /// @notice Check and emit verification event (state-changing for event log).
    function verify(bytes32 certId) external returns (bool success) {
        success = certified[certId];
        emit VerificationPerformed(certId, success, block.timestamp);
    }

    // ------------------------------------------------------------
    // VIEW FUNCTIONS (Phase 3: by certId; findByPayload)
    // ------------------------------------------------------------

    /// @notice Get the certificate by certId.
    /// @param certId Certificate ID (e.g. from vtn_uuid).
    /// @return cert Certificate data.
    function getCertificate(
        bytes32 certId
    ) external view returns (Certificate memory cert) {
        require(certified[certId], "Not certified");
        return certificates[certId];
    }

    /// @notice Returns whether a certId has been certified.
    function isCertified(bytes32 certId) external view returns (bool) {
        return certified[certId];
    }

    /// @notice Phase 3: Find certIds that have the given watermark payload.
    /// @param payload bytes4 watermark payload (e.g. first 4 bytes of SHA-256(cert_id)).
    /// @return certIds Array of certificate IDs with this payload (newest last if multiple).
    function findByPayload(bytes4 payload) external view returns (bytes32[] memory certIds) {
        return payloadIndex[payload];
    }

    /// @notice Get total number of certified content hashes.
    /// @return uint256 Number of certificates recorded.
    function getCertificateCount() external view returns (uint256) {
        return certificateCount;
    }
}

