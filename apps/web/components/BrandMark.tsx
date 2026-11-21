/** Simple drop over a field line — white on the green brand square. */
export default function BrandMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2.5c-3.2 4.1-5.5 7.4-5.5 10.2a5.5 5.5 0 0 0 11 0c0-2.8-2.3-6.1-5.5-10.2z" fill="#fff" />
      <path d="M3 21h18" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
