"use client";
import { ReactNode } from "react";
import { Shell } from "@/components/Shell";
import { ProjectProvider } from "@/lib/projectCtx";
import { ProjectFrame } from "@/components/ProjectNav";

export default function ProjectLayout({ children }: { children: ReactNode }) {
  return (
    <Shell>
      <ProjectProvider>
        <ProjectFrame>{children}</ProjectFrame>
      </ProjectProvider>
    </Shell>
  );
}
