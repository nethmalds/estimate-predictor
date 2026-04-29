import { ArrowUp, FileSpreadsheet, Plus } from "lucide-react";
import type { LucideProps } from "lucide-react";

type IconProps = LucideProps;

export function PlusIcon({ size = 16, ...props }: IconProps) {
  return <Plus aria-hidden="true" size={size} {...props} />;
}

export function SendIcon({ size = 16, ...props }: IconProps) {
  return <ArrowUp aria-hidden="true" size={size} {...props} />;
}

export function NewChatIcon({ size = 14, ...props }: IconProps) {
  return <Plus aria-hidden="true" size={size} {...props} />;
}

export function ExcelIcon({ size = 22, ...props }: IconProps) {
  return <FileSpreadsheet aria-hidden="true" size={size} {...props} />;
}
