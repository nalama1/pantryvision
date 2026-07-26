# Requirements Document

## Introduction

This feature upgrades the PantryVision frontend from a functional but unstyled React application to a production-ready, professional UI suitable for a hackathon demo. The application flow (upload photo → AI extraction → review form → confirm) remains unchanged. Only the visual layer is added and improved using plain CSS (no external UI frameworks or utility libraries).

## Glossary

- **Design_System**: A set of CSS custom properties and reusable style rules that define the visual identity (colors, typography, spacing, border-radius) of the application
- **Upload_Zone**: The interactive area where users can drag and drop or click to select a photo file for upload
- **Confidence_Badge**: A color-coded label displayed next to each extracted field indicating the AI's confidence level (high, medium, or low)
- **App_Shell**: The top-level layout structure including the header, main content area, and optional footer
- **Loading_State**: The visual state displayed while the application awaits a response from the AI extraction service
- **Success_State**: The visual confirmation displayed after a product has been successfully registered
- **Error_State**: The visual alert displayed when an operation fails, providing the user with clear messaging and recovery actions

## Requirements

### Requirement 1: Design System and CSS Custom Properties

**User Story:** As a developer, I want a centralized design system with CSS custom properties, so that all components share consistent visual styling without duplication.

#### Acceptance Criteria

1. THE Design_System SHALL define CSS custom properties for primary color (#232F3E), accent color (#FF9900), white (#FFFFFF), and at least three gray shades
2. THE Design_System SHALL define CSS custom properties for font-family, base font-size, and a type scale with at least three heading sizes
3. THE Design_System SHALL define CSS custom properties for spacing values (4px, 8px, 12px, 16px, 24px, 32px, 48px) and border-radius values (4px, 8px, 12px)
4. THE Design_System SHALL define a primary button style with the accent color background, white text, rounded corners, and a visible hover state
5. THE Design_System SHALL define a secondary button style with a transparent background, border, and a visible hover state
6. THE Design_System SHALL define a disabled button style with reduced opacity and a not-allowed cursor
7. THE Design_System SHALL define a card style with a white background, border-radius, and a soft box-shadow
8. THE Design_System SHALL define input field styles with a visible border, padding, border-radius, and a distinct focus state using outline or border-color change

### Requirement 2: Responsive Layout

**User Story:** As a user, I want the application to display correctly on my phone, tablet, or desktop, so that I can manage my pantry from any device.

#### Acceptance Criteria

1. THE App_Shell SHALL use a mobile-first approach where base styles target small screens and media queries enhance for larger viewports
2. THE App_Shell SHALL constrain the main content to a maximum width of 720px and center it horizontally
3. THE App_Shell SHALL apply consistent horizontal padding of at least 16px on screens narrower than 720px
4. THE App_Shell SHALL prevent horizontal scrolling on all viewport widths from 320px to 1920px
5. WHEN the viewport width is 768px or greater, THE App_Shell SHALL increase the main content padding and spacing to use available space

### Requirement 3: App Shell and Header

**User Story:** As a user, I want a clear app header and page structure, so that I can identify the application and navigate it easily.

#### Acceptance Criteria

1. THE App_Shell SHALL render a fixed or sticky header containing the application name "PantryVision" styled with the primary color as background and white text
2. THE App_Shell SHALL render section headings that clearly indicate the current step in the workflow (Upload, Extracting, Review, Done)
3. THE App_Shell SHALL apply vertical spacing between sections to visually separate content areas
4. THE App_Shell SHALL use the defined font-family and type scale from the Design_System for all text elements

### Requirement 4: Photo Upload Zone

**User Story:** As a user, I want a clear and inviting upload area, so that I understand how to add a product photo.

#### Acceptance Criteria

1. WHILE the Upload_Zone is in idle state, THE Upload_Zone SHALL display a dashed border, an upload icon, and instructional text indicating drag-and-drop or click-to-browse
2. WHEN a user drags a file over the Upload_Zone, THE Upload_Zone SHALL change its border color and background to provide a visual drop indication
3. THE Upload_Zone SHALL hide the native file input element and present styled buttons ("Select from gallery" and "Take a photo" when camera is available) using the Design_System button styles
4. WHEN a file is selected and previewing, THE Upload_Zone SHALL display the image preview at a minimum size of 200x200 pixels within a card-styled container
5. WHILE the Upload_Zone is in uploading state, THE Upload_Zone SHALL display a styled progress bar with a colored fill, percentage text, and rounded corners

### Requirement 5: AI Extraction Loading State

**User Story:** As a user, I want a professional loading indicator during AI extraction, so that I know the system is working and I can skip if needed.

#### Acceptance Criteria

1. WHILE the Loading_State is active, THE App_Shell SHALL display the message "Analyzing image with Amazon Bedrock..." centered on the page
2. WHILE the Loading_State is active, THE App_Shell SHALL display an animated spinner using CSS animation (rotation) with colors from the Design_System
3. WHILE the Loading_State is active, THE App_Shell SHALL display a "Skip to manual entry" button styled as a secondary button from the Design_System
4. THE Loading_State SHALL apply consistent vertical spacing between the message, spinner, and skip button

### Requirement 6: Review Form Styling

**User Story:** As a user, I want the extracted data review form to be clearly structured and easy to read, so that I can verify and correct product information efficiently.

#### Acceptance Criteria

1. THE ReviewForm SHALL be wrapped in a card-styled container with padding, border-radius, and box-shadow from the Design_System
2. THE ReviewForm SHALL display each field with a visible label above the input, using the Design_System input styles
3. WHEN a field has high confidence, THE Confidence_Badge SHALL display with a green background and text "High confidence"
4. WHEN a field has medium confidence, THE Confidence_Badge SHALL display with an amber/yellow background and text "Medium confidence"
5. WHEN a field has low confidence, THE Confidence_Badge SHALL display with a red background and text "Low confidence"
6. THE ReviewForm SHALL style the "Confirm" button as a primary button and the "Cancel" button as a secondary button from the Design_System
7. WHEN a validation error occurs, THE ReviewForm SHALL display the error message in red text immediately below the corresponding input field
8. IF an AI extraction error occurred, THEN THE ReviewForm SHALL display an alert-styled banner at the top of the form indicating manual entry is required

### Requirement 7: Success and Error States

**User Story:** As a user, I want clear visual feedback when operations succeed or fail, so that I know what happened and what to do next.

#### Acceptance Criteria

1. WHEN the product is successfully saved, THE Success_State SHALL display a card with a green checkmark icon, a confirmation message including the product name, and an "Upload Another" button styled as a primary button
2. WHEN the product is successfully saved, THE Success_State SHALL use a green accent color for the card border or icon to signal success
3. WHEN an upload error occurs, THE Error_State SHALL display a card with a red accent color, the error message, and action buttons (Retry and/or Try again)
4. THE Error_State SHALL use the Design_System card style with a red-tinted border or background to differentiate from other cards
5. THE Success_State and Error_State SHALL center their content within the card and use consistent spacing from the Design_System

### Requirement 8: Accessibility

**User Story:** As a user with accessibility needs, I want the application to meet accessibility standards, so that I can use it with assistive technologies and keyboard navigation.

#### Acceptance Criteria

1. THE Design_System SHALL ensure all text-to-background color combinations meet WCAG 2.1 AA contrast ratio (minimum 4.5:1 for normal text, 3:1 for large text)
2. THE Design_System SHALL provide a visible focus indicator (outline or ring) on all interactive elements (buttons, inputs, links) that is distinct from the default browser focus
3. THE App_Shell SHALL preserve all existing aria-label, aria-required, aria-invalid, aria-describedby, and role attributes already present in the components
4. THE Upload_Zone SHALL maintain keyboard operability for all file selection actions (gallery button and camera button are focusable and activatable via Enter/Space)
5. WHEN color is used to convey meaning (confidence levels, success/error states), THE Design_System SHALL also provide a non-color indicator (text label or icon) alongside the color

### Requirement 9: No New Dependencies

**User Story:** As a developer, I want the UI redesign to use only plain CSS, so that the project stays lightweight and avoids unnecessary build complexity.

#### Acceptance Criteria

1. THE Design_System SHALL be implemented using only plain CSS files imported into the React components or the main entry point
2. THE App_Shell SHALL NOT introduce any new npm packages (no CSS frameworks, no component libraries, no utility-first CSS tools)
3. THE Design_System SHALL use standard CSS features supported by modern browsers (CSS custom properties, flexbox, grid, media queries, transitions, animations)

### Requirement 10: Preservation of Existing Functionality

**User Story:** As a user, I want all existing features to keep working after the visual update, so that nothing breaks during the redesign.

#### Acceptance Criteria

1. THE App_Shell SHALL preserve the existing state machine flow (upload → extracting → review → done) without modification to the state transitions
2. THE PhotoUploader component SHALL retain all existing functionality including file validation, camera detection, presigned URL upload, retry logic, and progress tracking
3. THE ReviewForm component SHALL retain all existing functionality including field validation, confidence display, form submission, and cancel behavior
4. THE App_Shell SHALL preserve all existing data-testid attributes on components and elements to maintain test compatibility
