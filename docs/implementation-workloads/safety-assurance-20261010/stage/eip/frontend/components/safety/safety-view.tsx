"use client"

import { useMemo, useState } from "react"
import type { SafetyWorkspace as SafetyWorkspaceData, SafetyTreeNode } from "@/lib/eip/types"
import { SAFETY_KIND_SHORT } from "@/lib/eip/safety-labels"
import { TreeNavigator, type GenericTreeNode } from "@/components/eip/tree-navigator"
import { RiskAnalysisPanel, RiskDetailPanel } from "@/components/risk/risk-center-panels"
import { RiskMethodToolbar, RiskMethodResults } from "@/components/risk/risk-method-toolbar"
import { AssuranceDrafts } from "@/components/risk/assurance-drafts"

function filterTree(nodes: SafetyTreeNode[], q: string): SafetyTreeNode[] {
  if (!q) return nodes
  const out: SafetyTreeNode[] = []
  for (const n of nodes) {
    const children = filterTree(n.children, q)
    const selfMatch = n.label.toLowerCase().includes(q) || n.ref.toLowerCase().includes(q)
    if (selfMatch || children.length > 0) out.push({ ...n, children })
  }
  return out
}

export function SafetyView({ data, initialObject }: { data: SafetyWorkspaceData; initialObject?: string }) {
  const projectId = data.project.id
  const [selectedId, setSelectedId] = useState<string | null>(() => initialObject ? findNode(data.tree, initialObject)?.id ?? initialObject : null)
  const [method, setMethod] = useState(() => data.capabilities?.find((item) => item.available)?.id ?? "")
  const [query] = useState("")

  const q = query.trim().toLowerCase()
  const filteredTree = useMemo(() => filterTree(data.tree, q), [data.tree, q])
  const selectedNode = useMemo(() => selectedId ? findNode(data.tree, selectedId) : null, [data.tree, selectedId])
  const selectedRow = useMemo(() => selectedId ? data.analysis.find((row) => row.id === selectedId || row.ref === selectedId) ?? null : null, [data.analysis, selectedId])
  const selectedDetail = selectedId ? data.details[selectedId] ?? null : null

  return (
    <div className="flex h-full flex-col gap-4">

      <AssuranceDrafts projectId={projectId} method="nis-evidence" rows={data.draftAnalyses ?? []} total={data.draftAnalysisTotal ?? 0} canEdit={data.canEditAnalyses === true} />
      <RiskMethodToolbar domain="safety" projectId={projectId} selected={selectedNode} capabilities={data.capabilities} method={method} onMethodChange={setMethod} />

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 xl:grid-cols-12">
        <div className="min-h-[300px] overflow-hidden rounded-lg border border-border xl:col-span-3">
          <TreeNavigator
            title="Safety Explorer"
            subtitle="ASIL · Hazards · Safety Goals · Requirements"
            tree={filteredTree as unknown as GenericTreeNode[]}
            selectedId={selectedId}
            onSelect={(id) => setSelectedId((cur) => (cur === id ? null : id))}
            shortLabel={(kind) => SAFETY_KIND_SHORT[kind as keyof typeof SAFETY_KIND_SHORT] ?? kind}
            emptyMessage="Keine Safety-Daten im MRAS/Core. Verbinde eine Datenquelle, um HARA, Safety Goals, Requirements und Evidence zu sehen."
            ariaLabel="Safety-Explorer"
          />
        </div>

        <div className="flex min-w-0 flex-col gap-4 xl:col-span-6">
          <RiskMethodResults rows={data.methodRows ?? []} method={method} />
          <AssuranceDrafts projectId={projectId} method={method.startsWith("nis-") ? "" : method} rows={data.draftAnalyses ?? []} total={data.draftAnalysisTotal ?? 0} canEdit={data.canEditAnalyses === true} />
          <div className="flex min-h-[300px] flex-1 flex-col overflow-hidden rounded-lg border border-border bg-card">
            <RiskAnalysisPanel domain="safety" rows={data.analysis} selectedId={selectedId} onSelect={setSelectedId} />
          </div>
        </div>

        <div className="min-h-[300px] overflow-hidden rounded-lg border border-border xl:col-span-3">
          <RiskDetailPanel domain="safety" projectId={projectId} node={selectedNode} row={selectedRow} detail={selectedDetail} />
        </div>
      </div>
    </div>
  )
}

function findNode(nodes: SafetyTreeNode[], id: string): SafetyTreeNode | null {
  for (const node of nodes) {
    if (node.id === id || node.ref === id) return node
    const child = findNode(node.children, id)
    if (child) return child
  }
  return null
}
