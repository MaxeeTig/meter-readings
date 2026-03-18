# UI Description for AI Interface Generator

Create a **mobile-first web interface** for a local meter-reading service. 
Main job: user uploads a meter photo or takes live photo via camera, reviews OCR result, edits if needed, saves reading, then sees history and consumption chart.

## Product goals
- Fast data entry from phone browser.
- Mandatory human confirmation before save.
- Clear history and monthly/period consumption trend.
- Minimal taps, high readability in bright/outdoor conditions.

## Visual direction
- Style: clean utility UI, not decorative.
- Color system:
    suggest modern color palette 
- Border radius: 14px cards, 10px inputs/buttons.
- Shadows: subtle (`0 4px 14px rgba(15,23,42,0.08)`).
- Font: `Manrope` (fallback sans-serif), base 16px.

## App structure
Single-page layout with 4 vertical sections:
1. Header
2. Upload + OCR confirmation form
3. Readings history table/list
4. Consumption line chart

## Header
- Title: “Meter Readings”.
- Subtitle: “Upload photo, verify, save”.
- Right side (desktop): compact status badge (“Server online”/“Offline”).

## Upload + OCR section (primary card)
- File input zone with drag-and-drop + “Take/Choose Photo” button.
- Accepted formats hint: jpg, jpeg, png, webp, heic.
- After file selected:
  - Preview thumbnail
  - Button: “Recognize”
  - Progress bar + spinner while OCR request is running
- OCR result form fields:
  - Meter type (select): cold_water, hot_water, electricity
  - Reading value (numeric text input, allow decimal)
  - Reading datetime (datetime-local)
  - Notes (optional, textarea)
- Action buttons:
  - Primary: “Save Reading”
  - Secondary: “Submit to Portal” (active only if portal authorized and portal meter selected; uses edited Reading value)
  - Secondary: “Reset”
- Validation:
  - required: meter type, value, datetime
  - value must be non-negative number
  - inline errors under fields + top summary alert

## History section
- Title row with “Refresh” button.
- Mobile: card list; Desktop: table.
- Columns/fields:
  - Date/time
  - Meter type (colored tag)
  - Value
  - Source (OCR/manual)
- Sort newest first.
- Empty state text: “No readings yet. Add your first photo above.”

## Consumption chart section
- Line chart title: “Consumption Delta”.
- X-axis: reading dates.
- Y-axis: delta between neighboring readings.
- Legend by meter type (3 lines max).
- If insufficient data: neutral placeholder with hint text.

## API integration contract
- `POST /api/ocr` (multipart file) -> returns draft fields for form.
- `POST /api/readings` -> saves confirmed edited data.
- `GET /api/readings` -> populate history.
- `GET /api/reports/line` -> chart dataset.
- `POST /api/providers/mosenergosbyt/submit` -> submit edited reading to portal.

## Interaction rules
- Never auto-save OCR result without user click on “Save Reading”.
- After successful save:
  - show success toast
  - clear upload form
  - reload history + chart
- On API error:
  - sticky error banner with retry action
  - preserve user-entered values

## Responsive behavior
- Breakpoint at 900px.
- Mobile (<900): single column, fixed bottom action bar for primary actions.
- Desktop (>=900): two-column top area:
  - left: upload/OCR form
  - right: recent history snapshot
- Touch targets >=44px.

## Accessibility
- WCAG AA contrast.
- Full keyboard navigation.
- Proper labels/aria for all form controls.
- Live region announcements for OCR progress and save result.
