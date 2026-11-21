import Link from "next/link";

export default function HomePage() {
  return (
    <>
      <section className="hero">
        <div className="container hero-grid">
          <div>
            <h1>Sprawdź, jak zatrzymać wodę na swojej działce</h1>
            <p className="lead">
              {/* &nbsp; after one-letter words: Polish typography never leaves "W" / "i" alone at a line end */}
              Wskaż działkę na mapie albo wpisz jej numer. W&nbsp;kilkanaście sekund dostaniesz raport: jak sucho jest
              teraz, dlaczego i&nbsp;co możesz zrobić.
            </p>
            <Link href="/analizuj" className="btn btn-lg">
              Sprawdź działkę
            </Link>
            <p className="muted small" style={{ marginTop: 14 }}>
              Bezpłatnie, bez zakładania konta. Raport możesz wydrukować lub zapisać jako PDF.
            </p>
          </div>
          <div className="hero-figure" aria-hidden="true">
            <FieldsIllustration />
          </div>
        </div>
      </section>

      <section className="section" id="jak-to-dziala">
        <div className="container">
          <h2>Jak to działa</h2>
          <ol className="steps">
            <li>
              <span className="step-num">Krok 1</span>
              <h3>Wskaż działkę</h3>
              <p className="muted">Kliknij ją na mapie albo wpisz numer z wypisu z rejestru gruntów.</p>
            </li>
            <li>
              <span className="step-num">Krok 2</span>
              <h3>Wybierz uprawę</h3>
              <p className="muted">Różne rośliny potrzebują wody w różnym czasie — uwzględniamy to w ocenie.</p>
            </li>
            <li>
              <span className="step-num">Krok 3</span>
              <h3>Odbierz raport</h3>
              <p className="muted">Ocena, przyczyny i konkretne działania, z wyjaśnieniem, skąd to wiemy.</p>
            </li>
          </ol>
        </div>
      </section>

      <section className="section">
        <div className="container" style={{ maxWidth: 760, marginInline: "auto" }}>
          <h2>Co znajdziesz w raporcie</h2>
          <ol className="report-order">
            <li>
              <div>
                <strong>Ocena wilgotności</strong>
                <div className="muted">Jak sucho jest teraz i jak często na tej działce brakuje wody.</div>
              </div>
            </li>
            <li>
              <div>
                <strong>Przyczyny</strong>
                <div className="muted">Brak deszczu, gleba, która słabo trzyma wodę, spływ po spadku terenu.</div>
              </div>
            </li>
            <li>
              <div>
                <strong>Zatrzymanie wody i uprawa gleby</strong>
                <div className="muted">Pasy zieleni, zastawki na rowach, międzyplony, mniej orki.</div>
              </div>
            </li>
            <li>
              <div>
                <strong>
                  Nawadnianie <span className="opt">— tylko jeśli naprawdę potrzebne</span>
                </strong>
                <div className="muted">Na końcu, bo najtańsza woda to ta, którą zatrzymasz na polu.</div>
              </div>
            </li>
          </ol>
        </div>
      </section>

      <section className="section" id="dane">
        <div className="container">
          <h2>Skąd bierzemy dane</h2>
          <p style={{ maxWidth: "65ch" }}>
            Korzystamy wyłącznie z publicznych, otwartych danych. Raport liczymy na bieżąco dla Twojej działki. Zawsze
            pokazujemy źródło każdej liczby i mówimy wprost, jakich danych zabrakło.
          </p>
          <ul className="source-list">
            <li>
              <strong>Granice działek</strong> — GUGiK (ULDK, Geoportal)
            </li>
            <li>
              <strong>Pogoda z ostatnich 10 lat</strong> — Open-Meteo
            </li>
            <li>
              <strong>Gleba</strong> — ISRIC SoilGrids
            </li>
            <li>
              <strong>Ukształtowanie terenu</strong> — GUGiK (model terenu)
            </li>
            <li>
              <strong>Zdjęcia satelitarne</strong> — Copernicus Sentinel-2
            </li>
            <li>
              <strong>Susza rolnicza</strong> — IUNG-PIB (gdy dostępne)
            </li>
          </ul>
          <p className="muted small" style={{ maxWidth: "65ch" }}>
            Raport ma charakter doradczy. Nie zastępuje porady doradcy rolnego ani wymaganych pozwoleń (np. wodnoprawnych).
          </p>
        </div>
      </section>
    </>
  );
}

/** Flat illustration: field parcels from above, one highlighted. */
function FieldsIllustration() {
  const lines = "#c9d6cc";
  return (
    <svg viewBox="0 0 480 340" width="100%" style={{ display: "block" }}>
      <rect width="480" height="340" fill="#f1f5f1" />
      <g stroke={lines} strokeWidth="1.5">
        <path d="M0 0 L190 0 L170 120 L0 135 Z" fill="#e5ece0" />
        <path d="M190 0 L330 0 L318 105 L170 120 Z" fill="#eef2e6" />
        <path d="M330 0 L480 0 L480 95 L318 105 Z" fill="#e2eadb" />
        <path d="M0 135 L170 120 L158 230 L0 248 Z" fill="#eef2e6" />
        <path d="M318 105 L480 95 L480 205 L305 222 Z" fill="#e9efe3" />
        <path d="M0 248 L158 230 L150 340 L0 340 Z" fill="#e2eadb" />
        <path d="M158 230 L305 222 L298 340 L150 340 Z" fill="#e8eee2" />
        <path d="M305 222 L480 205 L480 340 L298 340 Z" fill="#eef2e6" />
      </g>
      {/* furrows on the highlighted plot */}
      <clipPath id="plot-clip">
        <path d="M170 120 L318 105 L305 222 L158 230 Z" />
      </clipPath>
      <g clipPath="url(#plot-clip)" stroke="#bfdcc9" strokeWidth="2">
        {Array.from({ length: 14 }, (_, i) => (
          <line key={i} x1={140} y1={110 + i * 10} x2={340} y2={95 + i * 10} />
        ))}
      </g>
      <path d="M170 120 L318 105 L305 222 L158 230 Z" fill="#0f6b3a" fillOpacity="0.12" stroke="#fff" strokeWidth="7" />
      <path d="M170 120 L318 105 L305 222 L158 230 Z" fill="none" stroke="#0f6b3a" strokeWidth="3" />
      {/* stream */}
      <path d="M0 300 C 80 280, 120 320, 200 300 S 340 260, 480 290" stroke="#7fb2d9" strokeWidth="6" fill="none" />
      {/* label */}
      <rect x="185" y="152" width="108" height="28" rx="4" fill="#0f6b3a" />
      <text x="239" y="171" textAnchor="middle" fontSize="14" fontWeight="700" fill="#fff" fontFamily="system-ui, sans-serif">
        Twoja działka
      </text>
      {/* drop */}
      <path d="M392 140c-9 11-15 20-15 27a15 15 0 0 0 30 0c0-7-6-16-15-27z" fill="#2f6fb3" />
    </svg>
  );
}
