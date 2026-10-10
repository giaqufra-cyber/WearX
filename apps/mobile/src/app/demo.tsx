import { Redirect } from "expo-router";

/**
 * `wearx://demo?server=…` (QR della demo): il collegamento lo fa DemoGate; qui si torna solo
 * all'inizio dell'app. Fuori dalla build demo l'indirizzo non fa nulla.
 */
export default function DemoLink() {
  return <Redirect href="/" />;
}
