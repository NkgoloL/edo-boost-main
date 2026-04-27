"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { ParentDashboard } from "../../../components/eduboost/ParentDashboard";

export default function ParentDashboardPage() {
  const router = useRouter();

  return <ParentDashboard onBack={() => router.push("/")} />;
}
