import type { ReportAdapter, ReportChapter } from "@/types/reportWorkspace";
import * as ra from "./riskAssessmentService";
import * as ri from "./resourceInvestigationService";

function chaptersFrom(report: { summary?: { chapters?: ReportChapter[] } }): ReportChapter[] {
  return report.summary?.chapters ?? [];
}

function makeAdapter(
  kind: "risk" | "resource",
): ReportAdapter {
  return {
    async load(enterpriseId) {
      const doc = kind === "risk"
        ? await ra.getRiskAssessment(enterpriseId)
        : await ri.getResourceInvestigation(enterpriseId);
      return {
        id: doc.id,
        title: doc.title,
        content: doc.content,
        status: doc.status,
        generatedAt: doc.generated_at ?? null,
        chapters: chaptersFrom(doc),
        stylePreference: doc.style_preference,
        fourColorImages: (doc.summary as
          | { images?: Array<{ floor_id: string; floor_name: string; url: string }> }
          | undefined)?.images ?? [],
      };
    },
    saveChapter: (enterpriseId, key, content) => kind === "risk"
      ? ra.saveRiskAssessmentSection(enterpriseId, key, content)
      : ri.saveResourceInvestigationSection(enterpriseId, key, content),
    generateChapter: (enterpriseId, key, cb) => kind === "risk"
      ? ra.generateRiskAssessmentSectionStream(enterpriseId, key, cb)
      : ri.generateResourceInvestigationSectionStream(enterpriseId, key, cb),
    regenerateChapter: (enterpriseId, key, cb) => kind === "risk"
      ? ra.generateRiskAssessmentSectionStream(enterpriseId, key, cb)
      : ri.generateResourceInvestigationSectionStream(enterpriseId, key, cb),
    generateAll: (enterpriseId, cb) => kind === "risk"
      ? ra.generateRiskAssessmentStream(enterpriseId, undefined, cb.onEvent, cb.onError, cb.onComplete)
      : ri.generateResourceInvestigationStream(enterpriseId, undefined, cb.onEvent, cb.onError, cb.onComplete),
    review: (enterpriseId, keys) => kind === "risk"
      ? ra.reviewRiskAssessment(enterpriseId, keys)
      : ri.reviewResourceInvestigation(enterpriseId, keys),
    applyReview: (enterpriseId, keys) => kind === "risk"
      ? ra.applyRiskAssessmentReview(enterpriseId, keys)
      : ri.applyResourceInvestigationReview(enterpriseId, keys),
    getStyle: (enterpriseId) => kind === "risk"
      ? ra.getRiskAssessmentStyle(enterpriseId)
      : ri.getResourceInvestigationStyle(enterpriseId),
    saveStyle: (enterpriseId, style) => kind === "risk"
      ? ra.saveRiskAssessmentStyle(enterpriseId, style)
      : ri.saveResourceInvestigationStyle(enterpriseId, style),
    merge: async (enterpriseId, chapters) => {
      if (kind === "risk") {
        await ra.mergeRiskAssessment(enterpriseId, chapters);
      } else {
        await ri.mergeResourceInvestigation(enterpriseId, chapters);
      }
    },
    listVersions: (enterpriseId) => kind === "risk"
      ? ra.listRiskAssessmentVersions(enterpriseId)
      : ri.listResourceInvestigationVersions(enterpriseId),
    download: (enterpriseId) => kind === "risk"
      ? ra.downloadRiskAssessment(enterpriseId)
      : ri.downloadResourceInvestigation(enterpriseId),
  };
}

export const riskAssessmentAdapter: ReportAdapter = makeAdapter("risk");
export const resourceInvestigationAdapter: ReportAdapter = makeAdapter("resource");
