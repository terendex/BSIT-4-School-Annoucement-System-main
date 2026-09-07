/**
 * Markdown -> HTML for announcement bodies.
 *
 * Rendering happens on the server and the result is passed through an
 * allowlist sanitiser, so a body can never inject script or event handlers
 * into the page.
 */
import { marked } from "marked";
import sanitizeHtml from "sanitize-html";

marked.setOptions({ gfm: true, breaks: true });

const SANITIZE_OPTIONS: sanitizeHtml.IOptions = {
  allowedTags: [
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "strong", "em", "del", "code", "pre", "blockquote",
    "ul", "ol", "li",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
  ],
  allowedAttributes: {
    a: ["href", "title"],
    img: ["src", "alt", "title", "loading"],
    td: ["colspan", "rowspan"],
    th: ["colspan", "rowspan"],
  },
  allowedSchemes: ["http", "https", "mailto", "tel"],
  allowedSchemesByTag: { img: ["http", "https"] },
  transformTags: {
    // Outbound links open safely in a new tab.
    a: (tagName, attribs) => ({
      tagName,
      attribs: { ...attribs, target: "_blank", rel: "noopener noreferrer nofollow" },
    }),
    img: (tagName, attribs) => ({
      tagName,
      attribs: { ...attribs, loading: "lazy" },
    }),
  },
  disallowedTagsMode: "discard",
};

/**
 * Wrap tables in their own scroller. Applied after sanitising, so this markup
 * is ours rather than anything the author could inject. A wide table then
 * scrolls inside the article instead of widening the whole page on a phone.
 */
function wrapTables(html: string): string {
  return html
    .replace(/<table(\s[^>]*)?>/g, '<div class="prose__scroll"><table$1>')
    .replace(/<\/table>/g, "</table></div>");
}

export function renderMarkdown(source: string): string {
  if (!source) return "";
  const html = marked.parse(source, { async: false }) as string;
  return wrapTables(sanitizeHtml(html, SANITIZE_OPTIONS));
}
