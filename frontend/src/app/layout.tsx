import "./globals.css";

export const metadata = {
  title: "Conversational BI",
  description: "Turn natural language into dashboards."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

