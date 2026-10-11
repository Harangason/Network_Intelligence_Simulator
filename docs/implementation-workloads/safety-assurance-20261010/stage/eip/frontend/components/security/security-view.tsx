"use client"

import { useMemo, useState } from "react"
import type { SecurityWorkspace as SecurityWorkspaceData, SecurityTreeNode } from "@/lib/eip/types"
import { SECURITY_KIND_SHORT } from "@/lib/eip/security-labels"
import { TreeNavigator, type GenericTreeNode } from "@/components/eip/tree-navigator"
import { RiskAnalysisPanel, RiskDetailPanel } from "@/components/risk/risk-center-panels"
import { RiskMethodToolbar, RiskMethodResults } from "@/components/risk/risk-method-toolbar"
import { AssuranceDrafts } from "@/components/risk/assurance-drafts"

function filterTree(nodes: SecurityTreeNode[], q: string): SecurityTreeNode[] {
  if (!q) return nodes
  const out: SecurityTreeNode[] = []
  for (const n of nodes) {
    const children = filterTree(n.children, q)
    const selfMatch = n.label.toLowerCase().includes(q) || n.ref.toLowerCase().includes(q)
    if (selfMatch || children.length > 0) out.push({ ...n, children })
  }
  return out
}

export function SecurityView({ data, initialObject }: { data: SecurityWorkspaceData; initialObject?: string }) {
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

      <AssuranceDrafts projectId={projectId} method="nis-security-evidence" rows={data.draftAnalyses ?? []} total={data.draftAnalysisTotal ?? 0} canEdit={data.canEditAnalyses === true} />
      <RiskMethodToolbar domain="security" projectId={projectId} selected={selectedNode} capabilities={data.capabilities} method={method} onMethodChange={setMethod} />

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 xl:grid-cols-12">
        <div className="min-h-[300px] overflow-hidden rounded-lg border border-border xl:col-span-3">
          <TreeNavigator
            title="Security Explorer"
            subtitle="Assets · Threats · Attack Paths · Controls"
            tree={filteredTree as unknown as GenericTreeNode[]}
            selectedId={selectedId}
            onSelect={(id) => setSelectedId((cur) => (cur === id ? null : id))}
            shortLabel={(kind) => SECURITY_KIND_SHORT[kind as keyof typeof SECURITY_KIND_SHORT] ?? kind}
            emptyMessage="Keine Security-Daten im MRAS/Core. Verbinde eine Datenquelle, um Threats, Attack Paths, Controls und Evidence zu sehen."
            ariaLabel="Security-Explorer"
          />
        </div>

        <div className="flex min-w-0 flex-col gap-4 xl:col-span-6">
          <RiskMethodResults rows={data.methodRows ?? []} method={method} />
          <AssuranceDrafts projectId={projectId} method={method.startsWith("nis-") ? "" : method} rows={data.draftAnalyses ?? []} total={data.draftAnalysisTotal ?? 0} canEdit={data.canEditAnalyses === true} />
          <div className="flex min-h-[300px] flex-1 flex-col overflow-hidden rounded-lg border border-border bg-card">
            <RiskAnalysisPanel domain="security" rows={data.analysis} selectedId={selectedId} onSelect={setSelectedId} />
          </div>
        </div>

        <div className="min-h-[300px] overflow-hidden rounded-lg border border-border xl:col-span-3">
          <RiskDetailPanel domain="security" projectId={projectId} node={selectedNode} row={selectedRow} detail={selectedDetail} />
        </div>
      </div>
    </div>
  )
}

function findNode(nodes: SecurityTreeNode[], id: string): SecurityTreeNode | null {
  for (const node of nodes) {
    if (node.id === id || node.ref === id) return node
    const child = findNode(node.children, id)
    if (child) return child
  }
  return null
}
