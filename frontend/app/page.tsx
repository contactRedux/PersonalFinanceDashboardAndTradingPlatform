import { redirect } from "next/navigation";

/**
 * Root page — redirects to the main dashboard.
 */
export default function RootPage() {
  redirect("/dashboard");
}
