/**
 * The poster maker's public surface: give it a template id and a bag of text,
 * get back the pages to draw and PNGs ready to attach to an announcement.
 *
 * A poster is usually one page. Longer ones - a full week's schedule, a list
 * of reminders per subject - continue onto a second and a third, each posted
 * as its own image, because the page itself never grows: it is the size
 * Messenger shows, and anything else would arrive shrunk.
 */

import type { Poster } from "./blocks";
import { layoutPoster, paintPage, type Layout } from "./layout";
import { PAGE_HEIGHT, PAGE_WIDTH } from "./theme";
import { TEMPLATE_BY_ID, TEMPLATES, templatesFor, type Field, type Template } from "./templates";

export type { Field, Template, Poster, Layout };
export { TEMPLATES, TEMPLATE_BY_ID, templatesFor, PAGE_WIDTH, PAGE_HEIGHT };

/**
 * Measuring needs a 2D context but not a visible canvas, and the preview
 * canvases are resized as they are drawn, so measurement happens on its own.
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
 * Works out the pages a poster needs. Where a template offered several
 * arrangements, the one that reads best is the one chosen.
 */
export function planPoster(
  templateId: string,
  values: Record<string, string>
): Layout | null {
  const ctx = measuringContext();
  const posters = postersFrom(templateId, values);
  if (!ctx || posters.length === 0) return null;
  return layoutPoster(ctx, posters);
}

export { paintPage };

/** A filename that says what the poster is without needing to open it. */
export function posterFilename(templateId: string, title: string, page = 0, pages = 1): string {
  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 60);
  const suffix = pages > 1 ? `-${page + 1}-of-${pages}` : "";
  return `${slug || templateId}-poster${suffix}.png`;
}

/** The caption an attached page carries, so the order is obvious later. */
export function pageCaption(templateName: string, page: number, pages: number): string {
  return pages > 1 ? `${templateName} (${page + 1} of ${pages})` : templateName;
}

/** One drawn canvas as a PNG file, ready for the attachments endpoint. */
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

/**
 * Every page of a laid-out poster as a PNG, in order. Drawn on a canvas of
 * its own rather than the preview's, so what is saved does not depend on what
 * happens to be on screen.
 */
export async function posterFiles(layout: Layout, title: string, templateId: string) {
  if (typeof document === "undefined") return [];
  const canvas = document.createElement("canvas");
  const files: File[] = [];

  for (let index = 0; index < layout.pages.length; index += 1) {
    paintPage(canvas, layout, index);
    files.push(
      await canvasToFile(
        canvas,
        posterFilename(templateId, title, index, layout.pages.length)
      )
    );
  }
  return files;
}
