"use client";

import Link from "next/link";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import "./globals.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function NavBar() {
  const pathname = usePathname();

  const links = [
    { href: "/", label: "Home" },
    { href: "/explorer", label: "Explorer" },
    { href: "/datasets", label: "Datasets" },
  ];

  return (
    <nav className="flex items-center gap-4 px-4 sm:px-6 h-12 border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm">
      <span className="text-sm font-semibold text-indigo-400 mr-4">CrMD</span>
      {links.map((link) => {
        const isActive = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            className={`text-sm transition-colors ${isActive ? "text-gray-100" : "text-gray-500 hover:text-gray-300"}`}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        <QueryClientProvider client={queryClient}>
          <NavBar />
          <main>{children}</main>
        </QueryClientProvider>
      </body>
    </html>
  );
}
