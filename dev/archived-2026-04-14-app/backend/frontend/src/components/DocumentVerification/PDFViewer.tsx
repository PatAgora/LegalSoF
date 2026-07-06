import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
// Bundle the PDF.js worker with the app rather than pulling it from a
// CDN. The app's Content-Security-Policy is `script-src 'self'`, which
// blocks a cross-origin (unpkg) worker - so the PDF never renders. The
// `?url` import makes Vite emit the worker as a same-origin asset.
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

interface PDFViewerProps {
  fileUrl: string;
  authToken: string;
  highlightPages?: number[];
  onPageCount?: (count: number) => void;
}

export default function PDFViewer({ fileUrl, authToken, highlightPages = [], onPageCount }: PDFViewerProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  const onDocumentLoadSuccess = useCallback(({ numPages: n }: { numPages: number }) => {
    setNumPages(n);
    setLoadError(null);
    onPageCount?.(n);
  }, [onPageCount]);

  const onDocumentLoadError = useCallback((error: Error) => {
    console.debug('PDF load error:', error);
    setLoadError('The document preview could not be loaded.');
  }, []);

  // react-pdf re-loads the document whenever the options object identity
  // changes - an inline literal would retrigger a load on every render.
  const documentOptions = useMemo(
    () => ({ httpHeaders: { Authorization: `Bearer ${authToken}` } }),
    [authToken],
  );

  // Fallback when the inline preview fails: fetch the original file with
  // the auth header and hand it to the browser as a download.
  const downloadOriginal = useCallback(async () => {
    try {
      const r = await fetch(fileUrl, { headers: { Authorization: `Bearer ${authToken}` } });
      if (!r.ok) return;
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = decodeURIComponent(fileUrl.split('/').pop() || 'document.pdf');
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      /* download is best-effort */
    }
  }, [fileUrl, authToken]);

  // Expose scroll-to-page functionality
  const scrollToPage = useCallback((pageNum: number) => {
    const el = pageRefs.current.get(pageNum);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, []);

  // Expose via ref-like pattern using window event
  useEffect(() => {
    const handler = (e: CustomEvent) => {
      if (e.detail?.fileUrl === fileUrl) {
        scrollToPage(e.detail.pageNum);
      }
    };
    window.addEventListener('pdf-scroll-to-page' as any, handler);
    return () => window.removeEventListener('pdf-scroll-to-page' as any, handler);
  }, [fileUrl, scrollToPage]);

  const highlightSet = new Set(highlightPages);

  return (
    <div ref={containerRef} className="h-full overflow-y-auto bg-gray-100 p-4">
      {loadError ? (
        <div className="flex items-center justify-center h-full">
          <div className="text-center p-6">
            <svg className="w-12 h-12 text-zinc-400 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="text-sm text-zinc-600">{loadError}</p>
            <button
              type="button"
              onClick={downloadOriginal}
              className="mt-3 text-sm font-medium text-zinc-900 underline underline-offset-2 hover:text-zinc-700"
            >
              Download original
            </button>
          </div>
        </div>
      ) : (
        <Document
          file={fileUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={onDocumentLoadError}
          options={documentOptions}
          loading={
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-600" />
                <p className="mt-2 text-sm text-zinc-600">Loading document...</p>
              </div>
            </div>
          }
        >
          {Array.from({ length: numPages }, (_, i) => {
            const pageNum = i; // 0-indexed to match backend page_numbers
            const isHighlighted = highlightSet.has(pageNum);
            return (
              <div
                key={i}
                ref={(el) => { if (el) pageRefs.current.set(pageNum, el); }}
                className={`mb-4 mx-auto shadow-md transition-all duration-300 ${
                  isHighlighted ? 'ring-4 ring-status-warning-400 ring-offset-2' : ''
                }`}
                style={{ maxWidth: '100%' }}
              >
                <div className="relative">
                  {isHighlighted && (
                    <div className="absolute top-2 right-2 z-10 px-2 py-0.5 bg-amber-500 text-white text-xs font-bold rounded shadow">
                      Page {i + 1}
                    </div>
                  )}
                  <Page
                    pageNumber={i + 1}
                    width={550}
                    renderTextLayer={true}
                    renderAnnotationLayer={true}
                  />
                </div>
                <div className="text-center text-xs text-zinc-400 py-1 bg-white">
                  Page {i + 1} of {numPages}
                </div>
              </div>
            );
          })}
        </Document>
      )}
    </div>
  );
}

// Helper to trigger page scroll from outside
export function scrollPDFToPage(fileUrl: string, pageNum: number) {
  window.dispatchEvent(new CustomEvent('pdf-scroll-to-page', { detail: { fileUrl, pageNum } }));
}
