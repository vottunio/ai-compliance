import { VottunComplianceClient } from "@vottun/ai-compliance";

async function main() {
  const client = new VottunComplianceClient(); // free testnet mode

  const cert = await client.certifyContent({
    content: "Hello world",
    ai_system: "gpt-4o"
  });

  console.log("cert:", cert);

  const certId = cert.cert_id ?? cert.certificate_id;
  if (certId) {
    const verified = await client.verifyCertificate(certId);
    console.log("verify:", verified);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

