type ModeSelectionPageProps = {
  onSelectMain: () => void;
  onSelectMobileCapture: () => void;
};

export function ModeSelectionPage({
  onSelectMain,
  onSelectMobileCapture
}: ModeSelectionPageProps) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-brand px-4">
      <main className="w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <div className="inline-flex items-center rounded-2xl bg-white px-4 py-3">
            <img src="/ati-logo/ATI-logo.png" alt="ATI Worksite Solutions" className="h-10 w-auto" />
          </div>
        </div>

        <section className="rounded-3xl border border-white/[0.07] bg-brand p-6 text-white">
          <p className="text-xs uppercase tracking-[0.3em] text-white/45">Select mode</p>
          <h1 className="mt-2 text-2xl font-semibold">Choose workflow</h1>

          <div className="mt-6 grid gap-3">
            <button
              className="rounded-2xl bg-accent px-5 py-4 text-base font-semibold text-white transition hover:opacity-90"
              onClick={onSelectMain}
              type="button"
            >
              Main Program
            </button>
            <button
              className="rounded-2xl border border-white/20 bg-white/10 px-5 py-4 text-base font-semibold text-white transition hover:bg-white/20"
              onClick={onSelectMobileCapture}
              type="button"
            >
              Mobile Capture
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}
