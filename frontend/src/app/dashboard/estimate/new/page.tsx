"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { submitWizardForm } from "@/services/estimates.service";
import {
  WizardFormData,
  WizardStepId,
  WIZARD_STEPS,
  ProjectBasics,
  FloorAreas,
  BuildingProgram,
  ConstructionDetails,
} from "@/types/wizard";
import { validateStep } from "@/lib/schemas/wizard";
import { WizardProgress } from "@/components/wizard/WizardProgress";
import { ProjectBasicsStep } from "@/components/wizard/steps/ProjectBasicsStep";
import { FloorAreasStep } from "@/components/wizard/steps/FloorAreasStep";
import { BuildingProgramStep } from "@/components/wizard/steps/BuildingProgramStep";
import { ConstructionDetailsStep } from "@/components/wizard/steps/ConstructionDetailsStep";
import { ReviewSubmitStep } from "@/components/wizard/steps/ReviewSubmitStep";
import { ChevronLeft, ChevronRight, Loader2, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

// --- Initial form state ---

const INITIAL_FORM: WizardFormData = {
  projectBasics: { building_type: "", floor_count: "", description: "", floorplan_urls: [] },
  floorAreas: { floor_areas: [] },
  buildingProgram: {},
  constructionDetails: {
    finish_level: "",
    structural_system: "",
    roof_type: "",
    ceiling_type: "",
    location: "",
    soil_condition: "",
    drainage_type: "",
    external_works_scope: "",
  },
};

// --- Flat payload builder for API ---

function buildApiPayload(form: WizardFormData): Record<string, unknown> {
  const { projectBasics, floorAreas, buildingProgram, constructionDetails } = form;
  return {
    building_type: projectBasics.building_type || undefined,
    floor_count: projectBasics.floor_count || undefined,
    description: projectBasics.description || undefined,
    floorplan_urls: projectBasics.floorplan_urls || [],
    floor_areas: floorAreas.floor_areas,
    ...buildingProgram,
    ...constructionDetails,
  };
}

// validateStep is imported from @/lib/schemas/wizard (zod-backed)

// --- Main component ---

export default function NewEstimatePage() {
  const { data: session } = useSession();
  const router = useRouter();
  const accessToken = (session?.user as { accessToken?: string } | undefined)?.accessToken ?? "";

  const [currentStep, setCurrentStep] = useState<WizardStepId>(1);
  const [formData, setFormData] = useState<WizardFormData>(INITIAL_FORM);
  const [stepErrors, setStepErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [started, setStarted] = useState(false);

  const handleNext = () => {
    const errors = validateStep(currentStep, formData);
    if (Object.keys(errors).length > 0) {
      setStepErrors(errors);
      return;
    }
    setStepErrors({});
    setCurrentStep((s) => Math.min(s + 1, 5) as WizardStepId);
  };

  const handleBack = () => {
    setStepErrors({});
    setCurrentStep((s) => Math.max(s - 1, 1) as WizardStepId);
  };

  const handleEditStep = (step: WizardStepId) => {
    setStepErrors({});
    setCurrentStep(step);
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const payload = buildApiPayload(formData);
      const { estimate_id } = await submitWizardForm(payload, accessToken || undefined);

      // Estimation is now running in the background on the server.
      // Immediately navigate to the detail page which shows live progress.
      setStarted(true);
      if (estimate_id) {
        router.push(`/dashboard/estimates/${estimate_id}`);
      } else {
        router.push("/dashboard/estimates");
      }
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Submission failed.");
      setIsSubmitting(false);
    }
  };

  // Brief "started" screen shown while router.push is navigating.
  if (started) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="max-w-sm text-center">
          <CheckCircle className="mx-auto mb-4 h-12 w-12 text-green-400" />
          <h2 className="mb-2 text-lg font-semibold text-zinc-900">Estimation Started!</h2>
          <p className="text-sm text-zinc-600">Redirecting to your estimate...</p>
        </div>
      </div>
    );
  }

  const floorCount = Number(formData.projectBasics.floor_count) || 1;

  return (
    <div className="relative mx-auto max-w-4xl space-y-6 overflow-hidden p-6">
      {/* Ambient glow */}
      <div className="pointer-events-none absolute -top-20 left-1/3 -z-10 h-[250px] w-[400px] rounded-full bg-blue-600/10 blur-[100px]" />

      <div>
        <h1 className="text-2xl font-bold text-zinc-900">Construction Cost Estimator</h1>
        <p className="mt-1 text-sm text-zinc-600">
          Complete the form to generate your Bill of Quantities estimate.
        </p>
      </div>

      <WizardProgress steps={WIZARD_STEPS} currentStep={currentStep} />

      <Card className="border-border/60 bg-card/80 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-zinc-900">{WIZARD_STEPS[currentStep - 1].title}</CardTitle>
          <CardDescription className="text-zinc-600">
            {WIZARD_STEPS[currentStep - 1].description}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {currentStep === 1 && (
            <ProjectBasicsStep
              data={formData.projectBasics}
              onChange={(d: ProjectBasics) => setFormData((f) => ({ ...f, projectBasics: d }))}
              errors={stepErrors}
            />
          )}
          {currentStep === 2 && (
            <FloorAreasStep
              data={formData.floorAreas}
              floorCount={floorCount}
              onChange={(d: FloorAreas) => setFormData((f) => ({ ...f, floorAreas: d }))}
              errors={stepErrors}
            />
          )}
          {currentStep === 3 && (
            <BuildingProgramStep
              data={formData.buildingProgram}
              buildingType={formData.projectBasics.building_type}
              onChange={(d: BuildingProgram) => setFormData((f) => ({ ...f, buildingProgram: d }))}
              errors={stepErrors}
            />
          )}
          {currentStep === 4 && (
            <ConstructionDetailsStep
              data={formData.constructionDetails}
              onChange={(d: ConstructionDetails) =>
                setFormData((f) => ({ ...f, constructionDetails: d }))
              }
              errors={stepErrors}
            />
          )}
          {currentStep === 5 && (
            <ReviewSubmitStep
              data={formData}
              onEditStep={handleEditStep}
              isSubmitting={isSubmitting}
              error={submitError}
            />
          )}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          onClick={handleBack}
          disabled={currentStep === 1}
          className="border-border/60 text-zinc-600 hover:text-zinc-900"
        >
          <ChevronLeft /> Back
        </Button>

        {currentStep < 5 ? (
          <Button
            onClick={handleNext}
            className="bg-blue-600 text-white shadow-lg shadow-blue-600/20 hover:bg-blue-500"
          >
            Next <ChevronRight />
          </Button>
        ) : (
          <Button
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="bg-blue-600 text-white shadow-lg shadow-blue-600/20 hover:bg-blue-500"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="animate-spin" /> Starting...
              </>
            ) : (
              "Generate Estimate"
            )}
          </Button>
        )}
      </div>
    </div>
  );
}
