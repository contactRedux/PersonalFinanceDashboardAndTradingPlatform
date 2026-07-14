/**
 * Auth route group layout.
 * Centered, minimal — no sidebar, no ticker tape.
 */
export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#000000",
        padding: "24px",
      }}
    >
      {children}
    </div>
  );
}
