/**
 * The poster maker's public surface: give it a template id and a bag of text,
 * get back a drawn canvas and a PNG ready to attach to an announcement.
 */

import type { Poster } from "./blocks";
import { fitBest, paint, type Fitted } from "./layout";
import { TEMPLATE_BY_ID, TEMPLATES, templatesFor, type Field, type Template } from "./templates";

export type { Field, Template, Poster, Fitted };
export { TEMPLATES, TEMPLATE_BY_ID, templatesFor };

/**
 * Measuring needs a 2D context but not a visible canvas, and the preview
 * canvas is resized mid-render, so measurement happens on its own scratch one.
 */
let scratch: CanvasRenderingContext2D | null = null;

function measuringContext(): CanvasRenderingContext2D | null {
  if (scratch) return scratch;
  if (typeof document === "undefined") return null;
  scratch = document.createElement("canvas").getContext("2d");
  return scratch;
}

/**
 * The posters a template makes from the publisher's words - usually one, but
 * a schedule offers the layout engine a choice of arrangements.
 */
export function postersFrom(templateId: string, values: Record<string, string>): Poster[] {
  const template = TEMPLATE_BY_ID.get(templateId);
  if (!template) return [];
  const built = template.build(values);
  return Array.isArray(built) ? built : [built];
}

/**
 * Draws a poster into `canvas`, sizing the canvas to whatever height the
 * content needed. Where a template offered several arrangements, the one that
 * fits best is the one drawn. Returns the fit so the editor can report the
 * final size and warn when the content overflowed.
 */
export function renderPoster(canvas: HTMLCanvasElement, posters: Poster[]): Fitted | null {
  const ctx = measuringContext();
  if (!ctx || posters.length === 0) return null;
  const { poster, fitted } = fitBest(ctx, posters);
  paint(canvas, poster, fitted);
  return fitted;
}

/** A filename that says what the poster is without needing to open it. */
export function posterFilename(templateId: string, title: string): string {
  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 60);
  return `${slug || templateId}-poster.png`;
}

/** The drawn canvas as a PNG file, ready for the attachments endpoint. */
export function canvasToFile(canvas: HTMLCanvasElement, filename: string): Promise<File> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error("The browser could not turn the poster into an image."));
        return;
      }
      resolve(new File([blob], filename, { type: "image/png" }));
    }, "image/png");
  });
}
