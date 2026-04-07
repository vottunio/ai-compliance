declare module "@coinbase/x402" {
  export function signPayment(privateKey: string, requirements: any): Promise<string | object>;
}
