/**
 * Menu OCR in the browser (open source, runs on the owner's device).
 *
 * PDF pages are rendered with pdf.js and read with tesseract.js; photos go
 * straight to tesseract.js. Only the recognised text (plus each PDF page's
 * embedded text layer, used server-side to correct misread prices and word
 * breaks) is sent to the server, so the small server never runs OCR.
 *
 * Lines are regrouped like the server's OCR: by row, and column by column on
 * two-column pages, so each dish stays on one line with its own price.
 */

export type PageText = { label: string; text: string; layer: string };
export type OcrProgress = { done: number; total: number };

// Exact versions (loaded on demand, only when someone uploads a menu).
const PDFJS = "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build";
const TARGET_WIDTH = 2000; // px a page is rendered at for OCR
const MAX_SIDE = 2400; // photos are downscaled to this

type Box = { y: number; h: number; x0: number; x1: number; text: string };

function rows(boxes: Box[]): string[] {
  const sorted = [...boxes].sort((a, b) => a.y - b.y || a.x0 - b.x0);
  const lines: Box[][] = [];
  for (const b of sorted) {
    const last = lines.at(-1)?.at(-1);
    if (last && Math.abs(last.y - b.y) < Math.max(b.h, last.h) * 0.6) lines.at(-1)!.push(b);
    else lines.push([b]);
  }
  return lines.map((l) =>
    l
      .sort((a, b) => a.x0 - b.x0)
      .map((b) => b.text)
      .filter(Boolean)
      .join("   "),
  );
}

const PRICE_ONLY = /^\W{0,2}[F?¥|丨IZ1%=<]{0,2}\d{2,5}(\.\d{1,2})?(\s*\/-)?$/;

/** Rows where `x` separates a dish from its right-aligned price (a gap inside one column). */
function splitsNameFromPrice(boxes: Box[], x: number): number {
  let count = 0;
  for (const b of boxes) {
    if (b.x0 < x || !PRICE_ONLY.test(b.text.replace(/\s/g, ""))) continue;
    const left = boxes.filter((o) => Math.abs(o.y - b.y) < Math.max(o.h, b.h) * 0.6 && o.x1 <= b.x0);
    if (left.length && Math.max(...left.map((o) => o.x1)) <= x) count++;
  }
  return count;
}

/** x of the empty band between two columns, if the page has two. */
function gutter(boxes: Box[], width: number): number | null {
  if (width <= 0 || boxes.length < 8) return null;
  const bins = 200;
  const step = width / bins;
  const crossings = new Array<number>(bins).fill(0);
  for (const b of boxes) {
    for (let i = Math.max(0, Math.floor(b.x0 / step)); i <= Math.min(bins - 1, Math.floor(b.x1 / step)); i++) crossings[i]++;
  }
  const allowed = Math.max(2, Math.floor(boxes.length / 15)); // titles/footers may span both
  const runs: [number, number][] = [];
  let run = 0;
  for (let i = Math.floor(bins * 0.3); i <= Math.floor(bins * 0.7); i++) {
    if (crossings[i] <= allowed) run++;
    else if (run) {
      runs.push([run, (i - run / 2) * step]);
      run = 0;
    }
  }
  runs.sort((a, b) => b[0] - a[0]);
  for (const [size, x] of runs) {
    if (size * step < width * 0.015) break;
    const left = boxes.filter((b) => b.x1 <= x).length;
    const right = boxes.filter((b) => b.x0 >= x).length;
    if (left >= 4 && right >= 4 && splitsNameFromPrice(boxes, x) < 2) return x;
  }
  return null;
}

export function toLines(boxes: Box[], width: number): string[] {
  const g = gutter(boxes, width);
  if (g === null) return rows(boxes);
  const left = boxes.filter((b) => b.x1 <= g);
  const right = boxes.filter((b) => b.x0 >= g);
  const spanning = boxes.filter((b) => b.x0 < g && g < b.x1);
  const top = Math.min(...[...left, ...right].map((b) => b.y));
  return [
    ...rows(spanning.filter((b) => b.y <= top)),
    ...rows(left),
    ...rows(right),
    ...rows(spanning.filter((b) => b.y > top)),
  ];
}

// ---------------------------------------------------------------------------

type TesseractWorker = {
  recognize: (
    image: HTMLCanvasElement,
    options?: object,
    output?: object,
  ) => Promise<{ data: { blocks: { paragraphs: { lines: { text: string; bbox: { x0: number; y0: number; x1: number; y1: number } }[] }[] }[] | null } }>;
  terminate: () => Promise<unknown>;
};

async function ocrCanvas(worker: TesseractWorker, canvas: HTMLCanvasElement): Promise<string> {
  const { data } = await worker.recognize(canvas, {}, { blocks: true, text: false });
  const boxes: Box[] = [];
  for (const block of data.blocks ?? []) {
    for (const para of block.paragraphs) {
      for (const line of para.lines) {
        const text = line.text.replace(/\s+/g, " ").trim();
        if (!text) continue;
        const { x0, y0, x1, y1 } = line.bbox;
        boxes.push({ y: (y0 + y1) / 2, h: y1 - y0, x0, x1, text });
      }
    }
  }
  return toLines(boxes, canvas.width).join("\n");
}

type PdfPage = {
  getViewport: (o: { scale: number }) => { width: number; height: number };
  getTextContent: () => Promise<{ items: { str?: string; hasEOL?: boolean }[] }>;
  render: (o: { canvasContext: CanvasRenderingContext2D; viewport: unknown }) => { promise: Promise<void> };
  cleanup: () => void;
};
type PdfDoc = { numPages: number; getPage: (n: number) => Promise<PdfPage>; destroy: () => Promise<void> };

async function loadPdfJs() {
  // Loaded from the CDN at runtime (not bundled): pdf.js is large and only
  // needed by the few visitors who upload a menu.
  const pdfjs = await import(/* webpackIgnore: true */ `${PDFJS}/pdf.min.mjs`);
  pdfjs.GlobalWorkerOptions.workerSrc = `${PDFJS}/pdf.worker.min.mjs`;
  return pdfjs as { getDocument: (o: { data: Uint8Array }) => { promise: Promise<PdfDoc> } };
}

async function renderPage(page: PdfPage): Promise<HTMLCanvasElement> {
  const base = page.getViewport({ scale: 1 });
  const viewport = page.getViewport({ scale: Math.min(3, TARGET_WIDTH / base.width) });
  const canvas = document.createElement("canvas");
  canvas.width = Math.ceil(viewport.width);
  canvas.height = Math.ceil(viewport.height);
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  await page.render({ canvasContext: ctx, viewport }).promise;
  return canvas;
}

async function photoCanvas(file: File): Promise<HTMLCanvasElement> {
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return canvas;
}

type Job = { label: string; canvas: () => Promise<HTMLCanvasElement>; layer: () => Promise<string>; done?: () => void };

/** OCR uploaded PDFs and photos on this device, a few pages at a time. */
export async function readMenuFiles(files: File[], onProgress?: (p: OcrProgress) => void): Promise<PageText[]> {
  const jobs: Job[] = [];
  const docs: PdfDoc[] = [];
  let pdfjs: Awaited<ReturnType<typeof loadPdfJs>> | null = null;
  for (const file of files) {
    if (file.type === "application/pdf") {
      pdfjs ??= await loadPdfJs();
      const doc = await pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) }).promise;
      docs.push(doc);
      for (let n = 1; n <= doc.numPages; n++) {
        let page: Promise<PdfPage> | null = null;
        const get = () => (page ??= doc.getPage(n));
        jobs.push({
          label: `${file.name} page ${n}`,
          canvas: async () => renderPage(await get()),
          layer: async () =>
            (await (await get()).getTextContent()).items.map((i) => (i.str ?? "") + (i.hasEOL ? "\n" : " ")).join(""),
          done: () => void get().then((p) => p.cleanup()),
        });
      }
    } else {
      jobs.push({ label: file.name, canvas: () => photoCanvas(file), layer: async () => "" });
    }
  }

  const { createWorker } = await import("tesseract.js");
  const cores = typeof navigator !== "undefined" ? navigator.hardwareConcurrency || 2 : 2;
  const count = Math.max(1, Math.min(4, Math.floor(cores / 2), jobs.length));
  const workers = (await Promise.all(
    Array.from({ length: count }, () => createWorker("eng")),
  )) as unknown as TesseractWorker[];

  const results: PageText[] = new Array(jobs.length);
  let next = 0;
  let done = 0;
  onProgress?.({ done, total: jobs.length });
  try {
    await Promise.all(
      workers.map(async (worker) => {
        while (next < jobs.length) {
          const i = next++;
          const job = jobs[i];
          const [canvas, layer] = await Promise.all([job.canvas(), job.layer()]);
          const text = await ocrCanvas(worker, canvas);
          canvas.width = canvas.height = 0; // free the bitmap memory
          job.done?.();
          results[i] = { label: job.label, text, layer };
          onProgress?.({ done: ++done, total: jobs.length });
        }
      }),
    );
  } finally {
    await Promise.all(workers.map((w) => w.terminate().catch(() => undefined)));
    await Promise.all(docs.map((d) => d.destroy().catch(() => undefined)));
  }
  return results;
}
