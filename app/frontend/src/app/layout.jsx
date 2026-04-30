import { LearnerProvider } from "../context/LearnerContext";
import { ServiceWorkerRegistration } from "../components/ServiceWorkerRegistration";
import "./globals.css";

export const metadata = {
  title: "EduBoost SA",
  description: "AI-powered learning for South African learners Grade R to Grade 7",
  manifest: "/manifest.json",
  themeColor: "#3b82f6",
  viewport: "width=device-width, initial-scale=1, maximum-scale=1",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <LearnerProvider>
          <ServiceWorkerRegistration />
          {children}
        </LearnerProvider>
      </body>
    </html>
  );
}
