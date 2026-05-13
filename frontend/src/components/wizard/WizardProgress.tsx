"use client";

import { WizardStep, WizardStepId } from "@/types/wizard";
import { Check } from "lucide-react";

interface Props {
  steps: WizardStep[];
  currentStep: WizardStepId;
}

export function WizardProgress({ steps, currentStep }: Props) {
  // Calculate progress percentage for the continuous line
  const progressPercent = ((currentStep - 1) / (steps.length - 1)) * 100;

  const currentStepObj = steps.find((s) => s.id === currentStep);

  return (
    <div
      role="progressbar"
      aria-valuenow={currentStep}
      aria-valuemin={1}
      aria-valuemax={steps.length}
      aria-label={`Step ${currentStep} of ${steps.length}: ${currentStepObj?.title ?? ""}`}
      className="relative z-0 mt-6 mb-16 px-2 sm:px-6"
    >
      {/* Background Track Line */}
      <div
        className="bg-border absolute top-4 right-6 left-6 -z-10 h-0.5 sm:right-10 sm:left-10"
        aria-hidden="true"
      >
        {/* Active Track Line */}
        <div
          className="absolute top-0 left-0 h-full bg-blue-600 transition-all duration-500 ease-out"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      <div className="flex items-start justify-between">
        {steps.map((step) => {
          const isCompleted = step.id < currentStep;
          const isCurrent = step.id === currentStep;

          return (
            <div key={step.id} className="relative z-10 flex flex-col items-center">
              {/* Step Circle */}
              <div
                aria-current={isCurrent ? "step" : undefined}
                className={`ring-background bg-background flex h-8 w-8 items-center justify-center rounded-full border-2 text-xs font-bold ring-[6px] transition-all duration-300 ${
                  isCompleted
                    ? "border-blue-600 bg-blue-600 text-white"
                    : isCurrent
                      ? "scale-110 border-blue-500 text-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.3)]"
                      : "border-border text-muted-foreground"
                }`}
              >
                {isCompleted ? (
                  <>
                    <Check className="h-4 w-4 stroke-3" aria-hidden="true" />
                    <span className="sr-only">{step.title} — completed</span>
                  </>
                ) : (
                  <span aria-hidden="true">{step.id}</span>
                )}
              </div>

              {/* Step Title */}
              <div className="absolute top-11 left-1/2 w-24 -translate-x-1/2 text-center sm:w-32">
                <span
                  className={`text-[10px] font-medium transition-colors duration-300 sm:text-xs ${
                    isCurrent
                      ? "text-blue-400"
                      : isCompleted
                        ? "text-foreground"
                        : "text-muted-foreground"
                  }`}
                >
                  {step.title}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
