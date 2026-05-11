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

  return (
    <div className="relative z-0 mb-16 mt-6 px-2 sm:px-6">
      {/* Background Track Line */}
      <div className="absolute top-4 left-6 right-6 sm:left-10 sm:right-10 h-0.5 bg-border -z-10">
        {/* Active Track Line */}
        <div
          className="absolute top-0 left-0 h-full bg-blue-600 transition-all duration-500 ease-out"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      <div className="flex justify-between items-start">
        {steps.map((step) => {
          const isCompleted = step.id < currentStep;
          const isCurrent = step.id === currentStep;

          return (
            <div key={step.id} className="flex flex-col items-center relative z-10">
              {/* Step Circle */}
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-all duration-300 ring-[6px] ring-background bg-background ${
                  isCompleted
                    ? "border-blue-600 bg-blue-600 text-white"
                    : isCurrent
                    ? "border-blue-500 text-blue-400 scale-110 shadow-[0_0_15px_rgba(59,130,246,0.3)]"
                    : "border-border text-muted-foreground"
                }`}
              >
                {isCompleted ? <Check className="w-4 h-4 stroke-3" /> : step.id}
              </div>
              
              {/* Step Title */}
              <div className="absolute top-11 w-24 sm:w-32 text-center left-1/2 -translate-x-1/2">
                <span
                  className={`text-[10px] sm:text-xs font-medium transition-colors duration-300 ${
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
