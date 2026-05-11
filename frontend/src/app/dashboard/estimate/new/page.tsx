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
    finish_level: "", structural_system: "", roof_type: "", ceiling_type: "",
    location: "", soil_condition: "", drainage_type: "", external_works_scope: "",
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

// --- Step validation ---

function validateStep(step: WizardStepId, form: WizardFormData): Record<string, string> {
  const errors: Record<string, string> = {};
  if (step === 1) {
    if (!form.projectBasics.building_type) errors.building_type = "Please select a building type.";
    const fc = Number(form.projectBasics.floor_count);
    if (!fc || fc < 1 || fc > 100) errors.floor_count = "Floor count must be between 1 and 100.";
  }
  if (step === 2) {
    if (!form.floorAreas.floor_areas.length) {
      errors.floor_areas = "Please enter area for at least one floor.";
    } else {
      form.floorAreas.floor_areas.forEach((row, i) => {
        const v = typeof row.area_value === "number" ? row.area_value : parseFloat(String(row.area_value));
        if (!v || v <= 0) errors["floor_areas[" + i + "]"] = row.floor_label + " area must be greater than zero.";
      });
    }
  }
  if (step === 3 && form.projectBasics.building_type === "residential") {
    const b = Number(form.buildingProgram.bedrooms);
    if (!b || b < 1 || b > 50) errors.bedrooms = "Please enter a valid number of bedrooms (1-50).";
    const bt = Number(form.buildingProgram.bathrooms);
    if (!bt || bt < 1 || bt > 50) errors.bathrooms = "Please enter a valid number of bathrooms (1-50).";
  }
  if (step === 3 && form.projectBasics.building_type === "commercial") {
    const wc = Number(form.buildingProgram.washroom_count);
    if (!wc || wc < 1) errors.washroom_count = "Commercial buildings must have at least 1 washroom.";
  }
  if (step === 4) {
    if (!form.constructionDetails.finish_level) errors.finish_level = "Please select a finish level.";
    if (!form.constructionDetails.structural_system) errors.structural_system = "Please select a structural system.";
    if (!form.constructionDetails.roof_type) errors.roof_type = "Please select a roof type.";
    if (!form.constructionDetails.ceiling_type) errors.ceiling_type = "Please select a ceiling type.";
  }
  return errors;
}

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
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center max-w-sm">
          <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-zinc-100 mb-2">Estimation Started!</h2>
          <p className="text-zinc-400 text-sm">Redirecting to your estimate...</p>
        </div>
      </div>
    );
  }

  const floorCount = Number(formData.projectBasics.floor_count) || 1;

  return (
    <div className="relative p-6 max-w-4xl mx-auto space-y-6 overflow-hidden">
      {/* Ambient glow */}
      <div className="absolute -top-20 left-1/3 w-[400px] h-[250px] bg-blue-600/10 blur-[100px] rounded-full pointer-events-none -z-10" />

      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Construction Cost Estimator</h1>
        <p className="text-zinc-400 text-sm mt-1">Complete the form to generate your Bill of Quantities estimate.</p>
      </div>

      <WizardProgress steps={WIZARD_STEPS} currentStep={currentStep} />

      <Card className="border-border/60 bg-card/80 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-zinc-100">{WIZARD_STEPS[currentStep - 1].title}</CardTitle>
          <CardDescription className="text-zinc-400">{WIZARD_STEPS[currentStep - 1].description}</CardDescription>
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
              onChange={(d: ConstructionDetails) => setFormData((f) => ({ ...f, constructionDetails: d }))}
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
        <Button variant="outline" onClick={handleBack} disabled={currentStep === 1}
          className="border-border/60 text-zinc-300 hover:text-zinc-100">
          <ChevronLeft /> Back
        </Button>

        {currentStep < 5 ? (
          <Button onClick={handleNext} className="bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/20">
            Next <ChevronRight />
          </Button>
        ) : (
          <Button onClick={handleSubmit} disabled={isSubmitting}
            className="bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/20">
            {isSubmitting ? <><Loader2 className="animate-spin" /> Starting...</> : "Generate Estimate"}
          </Button>
        )}
      </div>
    </div>
  );
}
