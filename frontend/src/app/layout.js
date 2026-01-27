import { Nunito_Sans, Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const nunitoSans = Nunito_Sans({
  subsets: ["latin"]
})

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata = {
  title: "TLC ChatMate",
  description: "TLC ChatMate: A Web-based Conversational Agent for The Lewis College",
  icons: {
    icon: ["/logo/logo.png"]
  }
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" type="image/png" sizes="32x32" href="/logo/logo.png" />
      </head>
      <body className={`${nunitoSans.className} ${geistSans.variable} ${geistMono.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
