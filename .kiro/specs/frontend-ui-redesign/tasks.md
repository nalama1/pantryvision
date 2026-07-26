# Implementation Plan: Frontend UI Redesign

## Overview

CSS-only visual upgrade for the PantryVision frontend. Creates a design system with tokens, adds component-specific stylesheets, and wires them into existing React components with minimal TSX changes (CSS imports + drag-and-drop class toggle + wrapper markup). No new npm dependencies, no component logic changes.

## Tasks

- [ ] 1. Create global design system stylesheet
  - [ ] 1.1 Create `src/styles/global.css` with design tokens, reset, and shared classes
    - Define all CSS custom properties on `:root` (colors, typography, spacing, border-radius, shadows)
    - Add minimal CSS reset (box-sizing, margin removal, font inheritance)
    - Add base typography rules (body font-family, heading scale)
    - Add shared `.btn`, `.btn--primary`, `.btn--secondary`, `.btn:disabled` button styles
    - Add shared `.input` and `.input:focus` styles
    - Add shared `.card` style
    - Add `@keyframes spin` animation for the loading spinner
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 8.1, 8.2, 9.1, 9.3_

- [ ] 2. Create component CSS files
  - [ ] 2.1 Create `src/styles/App.css` with app shell layout styles
    - Sticky header (`.app-header`): primary background, white text, padding
    - Main container (`.app-main`): max-width 720px, centered, horizontal padding
    - Section spacing between content areas
    - Extracting state: centered spinner + message + skip button layout
    - Done state: success card styling with green accent
    - Responsive breakpoint at 768px (increased padding/spacing)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 5.1, 5.2, 5.3, 5.4, 7.1, 7.2, 7.5_

  - [ ] 2.2 Create `src/components/PhotoUploader/PhotoUploader.css`
    - Upload zone idle state: dashed border, centered icon/text, gray-50 background
    - Drag-over state (`.photo-uploader__dropzone--dragover`): accent border + tinted background
    - File input hidden, styled buttons for gallery/camera
    - Image preview: min 200px, object-fit contain, inside card
    - Progress bar: container with fill element, rounded, accent color, width transition
    - Error state card with red accent
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 7.3, 7.4, 8.4_

  - [ ] 2.3 Create `src/components/ReviewForm/ReviewForm.css`
    - Card wrapper with padding, border-radius, box-shadow
    - Field layout: label above input, vertical spacing
    - Confidence badges: `.review-form__confidence--high` (green), `--medium` (amber), `--low` (red) as pills
    - Extraction error banner: warning background, left border, icon
    - Validation error text: red, small font, below input
    - Confirm/Cancel button layout using `.btn--primary` and `.btn--secondary`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 8.5_

- [ ] 3. Update TSX files to import CSS and add markup
  - [ ] 3.1 Update `src/main.tsx` to import `./styles/global.css`
    - Add `import './styles/global.css';` at the top of the file
    - _Requirements: 9.1_

  - [ ] 3.2 Update `src/App.tsx` to import App.css and add header/wrapper markup
    - Add `import '../styles/App.css';` (or correct relative path)
    - Add `<header className="app-header">` with app name "PantryVision"
    - Wrap main content in `<main className="app-main">`
    - Add section wrapper divs with appropriate class names for each state
    - Preserve all existing state logic, data-testid attributes, and event handlers
    - _Requirements: 3.1, 3.2, 3.3, 5.1, 5.2, 5.3, 10.1, 10.4_

  - [ ] 3.3 Update `src/components/PhotoUploader/PhotoUploader.tsx` to import CSS and add drag-and-drop visual toggle
    - Add `import './PhotoUploader.css';`
    - Add a wrapper div with class `photo-uploader__dropzone`
    - Add `onDragEnter`, `onDragLeave`, `onDrop` handlers that toggle `photo-uploader__dropzone--dragover` class via state
    - Preserve all existing functionality (file validation, upload, retry, progress)
    - _Requirements: 4.1, 4.2, 10.2_

  - [ ] 3.4 Update `src/components/ReviewForm/ReviewForm.tsx` to import CSS
    - Add `import './ReviewForm.css';`
    - Verify existing className attributes align with CSS classes (adjust class names if needed)
    - Preserve all existing functionality (validation, submission, cancel)
    - _Requirements: 6.1, 10.3_

- [ ] 4. Checkpoint — Verify build and existing tests pass
  - Run `npx tsc --noEmit` to confirm TypeScript compiles without errors
  - Run `npx vitest --run` to confirm all existing tests still pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 5. Write unit tests for CSS class application
  - [ ]* 5.1 Write tests verifying drag-and-drop class toggle on PhotoUploader
    - Test that `photo-uploader__dropzone--dragover` is added on dragenter and removed on dragleave/drop
    - _Requirements: 4.2, 10.2_
  - [ ]* 5.2 Write tests verifying header and layout classes render in App
    - Test that `.app-header` and `.app-main` elements are present
    - Test that state-specific classes appear for extracting/done states
    - _Requirements: 3.1, 3.2, 7.1_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP delivery
- This is all CSS work plus minimal TSX markup additions — no logic changes
- The drag-and-drop class toggle in PhotoUploader is the only new JS behavior (a simple boolean state for a CSS class)
- All existing tests must continue to pass since component logic is unchanged
- The design does not include a Correctness Properties section, so no property-based tests are needed

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "2.2", "2.3"] },
    { "id": 2, "tasks": ["3.1", "3.2", "3.3", "3.4"] },
    { "id": 3, "tasks": ["5.1", "5.2"] }
  ]
}
```
