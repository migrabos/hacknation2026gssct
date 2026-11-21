import Link from "next/link";

export default function NotFound() {
  return (
    <div className="container" style={{ paddingBlock: 48, maxWidth: 640 }}>
      <h1>Nie ma takiej strony</h1>
      <p>Strona, której szukasz, nie istnieje albo została przeniesiona.</p>
      <Link href="/" className="btn">
        Wróć na stronę główną
      </Link>
    </div>
  );
}
