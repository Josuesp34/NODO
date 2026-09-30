"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/components/product-shell";
import { LoadingState } from "@/components/ui";

export default function AppEntry() {
  const { capabilities } = useSession();
  const router = useRouter();
  useEffect(() => {
    router.replace(capabilities.includes("coach") || capabilities.includes("staff") ? "/coach" : "/athlete/today");
  }, [capabilities, router]);
  return <LoadingState label="Preparando tu espacio" />;
}
