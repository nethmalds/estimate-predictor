# Dashboard UI Refinement Plan

## Goal
Refine the dashboard UI to use shadcn for every UI aspect that can reasonably be mapped to a shadcn primitive, while keeping the existing estimate lifecycle behavior intact.

## Current Audit Summary
The dashboard pages themselves are already partially converted to shadcn, but several shared and adjacent UI surfaces still rely on raw Tailwind structures and hardcoded zinc-based styling.

### Remaining raw UI hotspots
- `frontend/src/components/layout/Sidebar.tsx`
- `frontend/src/components/results/ResultsComponents.tsx`
- `frontend/src/components/wizard/WizardProgress.tsx`
- `frontend/src/app/dashboard/estimates/[id]/EstimateDetailClient.tsx` stage timeline color treatment
- `frontend/src/app/dashboard/estimates/EstimatesListClient.tsx` inline delete confirmation pattern
- `frontend/src/app/dashboard/estimates/[id]/EstimateDetailClient.tsx` inline delete confirmation pattern
- `frontend/src/app/dashboard/page.tsx` and `frontend/src/app/dashboard/estimates/EstimatesListClient.tsx` still use custom list/grid structures where shadcn `Table` is a better fit

## Scope
This plan covers the attached dashboard folder and the shared UI components those screens depend on.

### In scope
- Dashboard layout shell
- Sidebar navigation
- Dashboard overview page
- Estimate list page and client actions
- Estimate detail page and client UI
- New estimate wizard page shell
- Results cards and BOQ table used inside estimate detail
- Wizard progress component used inside the dashboard flow

### Out of scope
- Wizard step field components such as `ProjectBasicsStep`, `FloorAreasStep`, `BuildingProgramStep`, `ConstructionDetailsStep`, and `ReviewSubmitStep`
- Backend behavior or API changes
- Recharts charting internals beyond their surrounding UI containers

## Design Decision
The sidebar should remain fixed-width and always open.

### Implication
- Use shadcn sidebar primitives internally
- Do not add a sidebar collapse trigger
- Still use `SidebarProvider`, because the shadcn sidebar primitives depend on it

## Phase 1: Install Missing shadcn Components
Add the remaining primitives needed to complete the conversion.

### Command
`npx shadcn@latest add table tooltip alert-dialog avatar`

### Why
The current dashboard still lacks shadcn support for:
- Table layouts
- Tooltips for icon-only actions
- Modal confirmation dialogs
- User avatar presentation in the sidebar footer

## Phase 2: Refine Dashboard Layout and Sidebar

### Files
- `frontend/src/components/layout/Sidebar.tsx`
- `frontend/src/app/dashboard/layout.tsx`

### Sidebar changes
Rewrite the sidebar using shadcn sidebar primitives:
- `Sidebar`
- `SidebarHeader`
- `SidebarContent`
- `SidebarGroup`
- `SidebarMenu`
- `SidebarMenuItem`
- `SidebarMenuButton`
- `SidebarFooter`
- `Avatar`
- `Button`

### Sidebar behavior
- Keep it always open
- Preserve current navigation destinations
- Preserve active-route highlighting
- Replace raw link/button styling with shadcn semantics
- Use a shadcn ghost icon button for sign-out
- Add avatar-based user summary in the footer

### Layout changes
Update the dashboard layout shell to:
- Wrap the page in `SidebarProvider`
- Replace the manual `ml-64` content offset with `SidebarInset`
- Remove hardcoded dashboard background and text color wrappers when shadcn layout primitives already own the structure

## Phase 3: Refine Results UI Components

### File
- `frontend/src/components/results/ResultsComponents.tsx`

This file is the largest remaining raw-UI surface and should be treated as a primary refinement target.

### CostBreakdownChart
Replace the current raw container with:
- `Card`
- `CardHeader`
- `CardTitle`
- `CardContent`

### ConfidenceBreakdownCard
Replace the raw container with:
- `Card`
- `CardHeader`
- `CardTitle`
- `CardContent`

Add stronger shadcn presentation for breakdown rows:
- `Badge variant="outline"` for threshold states
- `Progress` for confidence contribution or section score visualization where appropriate

### FullBoqTable
Replace the current custom structure with shadcn equivalents:
- Outer wrapper -> `Card`
- Header row -> `CardHeader`
- Filter input -> `Input`
- Table markup -> `Table`, `TableHeader`, `TableBody`, `TableRow`, `TableHead`, `TableCell`, `TableFooter`
- Pagination controls -> `Button variant="outline" size="sm"`
- Match-type pills -> `Badge variant="outline"`

### Match badge standardization
Create a single badge style mapping for match states such as:
- confirmed
- contractual
- soft_match
- no_match

This should follow the same pattern already used for estimate status badges.

## Phase 4: Replace Inline Delete Confirmations with AlertDialog

### Files
- `frontend/src/app/dashboard/estimates/EstimatesListClient.tsx`
- `frontend/src/app/dashboard/estimates/[id]/EstimateDetailClient.tsx`

### Current issue
Delete confirmation is currently rendered inline through temporary button swaps. That works functionally, but it is not a polished shadcn interaction and causes action rows to shift visually.

### Target pattern
Use:
- `AlertDialog`
- `AlertDialogTrigger`
- `AlertDialogContent`
- `AlertDialogHeader`
- `AlertDialogTitle`
- `AlertDialogDescription`
- `AlertDialogFooter`
- `AlertDialogCancel`
- `AlertDialogAction`

### Replace in these areas
- Estimate list row actions
- Estimate detail completed-state action bar
- Estimate detail cancelled or failed state action group

## Phase 5: Replace Native Titles with Tooltip

### Files
- `frontend/src/app/dashboard/estimates/EstimatesListClient.tsx`
- `frontend/src/app/dashboard/estimates/[id]/EstimateDetailClient.tsx`

### Current issue
Some icon buttons still rely on `title` attributes. That is a fallback, not a proper shadcn UI interaction.

### Target pattern
Use:
- `TooltipProvider`
- `Tooltip`
- `TooltipTrigger`
- `TooltipContent`

### Apply to
- Regenerate icon button
- Delete icon button
- Any icon-only action buttons in the estimate views

## Phase 6: Normalize the Estimate Progress Timeline Styling

### File
- `frontend/src/app/dashboard/estimates/[id]/EstimateDetailClient.tsx`

### Current issue
The structure is good, but the stage rows still use raw, hardcoded visual tokens such as:
- `bg-zinc-900`
- `bg-zinc-900/50`
- `bg-blue-950/60`
- `border-blue-700/50`
- `bg-red-950/40`
- `text-zinc-600`

### Refinement target
Keep the current timeline structure, but move the visual language toward semantic tokens and shadcn-compatible styling:
- active rows -> `bg-blue-500/10 border-blue-500/20`
- failed rows -> `bg-destructive/10 border-destructive/20`
- pending rows -> `bg-muted/40`
- neutral text -> `text-muted-foreground`
- neutral borders -> `border-border`

### Reasoning
There is no direct shadcn timeline primitive here, so this part should be refined through semantic token cleanup rather than a structural rewrite.

## Phase 7: Normalize Wizard Progress Styling

### File
- `frontend/src/components/wizard/WizardProgress.tsx`

### Current issue
The component is structurally fine, but all styling is still tied to raw zinc tokens.

### Refinement target
Keep the stepper structure, but replace hardcoded palette usage with semantic styling:
- Track line -> `bg-border`
- Completed step -> keep primary accent treatment
- Pending border -> `border-border`
- Pending text -> `text-muted-foreground`
- Outer ring -> `ring-background`
- Completed label text -> `text-foreground`

### Reasoning
There is no direct shadcn stepper primitive in this codebase, so the correct move is to retain structure and normalize tokens.

## Phase 8: Upgrade List Surfaces to shadcn Table

### Files
- `frontend/src/app/dashboard/page.tsx`
- `frontend/src/app/dashboard/estimates/EstimatesListClient.tsx`

### Dashboard recent estimates
Replace the custom divided list with a shadcn `Table` so the overview page matches the same visual grammar as the estimates page.

### Estimates list page
Replace the current CSS-grid row layout with shadcn `Table` primitives:
- `Table`
- `TableHeader`
- `TableRow`
- `TableHead`
- `TableBody`
- `TableCell`

### Benefits
- Better semantic structure
- Better alignment consistency
- Better reuse of shared table styles
- Stronger visual consistency across dashboard surfaces

## Phase 9: Final Validation

### Validation command
`npm run build`

### Success criteria
- Build passes with zero TypeScript errors
- Dashboard routes render cleanly
- Sidebar remains fixed-width and stable
- BOQ table uses shadcn table primitives
- Delete actions use `AlertDialog`
- Icon-only actions use `Tooltip`
- No dashboard-owned surface depends on raw button, input, dialog, badge, or table markup when a shadcn component exists for that purpose

## Implementation Order
1. Install missing shadcn components
2. Rewrite sidebar and dashboard layout shell
3. Rewrite `ResultsComponents.tsx`
4. Add `AlertDialog` delete flows
5. Add `Tooltip` to icon-only actions
6. Normalize progress timeline tokens
7. Normalize `WizardProgress` tokens
8. Convert remaining list/grid surfaces to shadcn `Table`
9. Run build validation

## File-Level Change List
- `frontend/src/components/layout/Sidebar.tsx`
- `frontend/src/app/dashboard/layout.tsx`
- `frontend/src/components/results/ResultsComponents.tsx`
- `frontend/src/app/dashboard/page.tsx`
- `frontend/src/app/dashboard/estimates/EstimatesListClient.tsx`
- `frontend/src/app/dashboard/estimates/[id]/EstimateDetailClient.tsx`
- `frontend/src/components/wizard/WizardProgress.tsx`

## Notes
- Recharts remains in place for charts; only the surrounding UI shell should be converted to shadcn
- Wizard step content components are intentionally excluded because they are not part of the attached dashboard surface
- The plan focuses on replacing raw UI structure, not changing estimate lifecycle logic or data flow