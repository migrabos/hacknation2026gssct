const scenes = {
  parcel: (
    <>
      <path d="M0 15 260 0v88L0 104Z" fill="#cbd7a4" />
      <path d="m-10 80 202-95M54 110 234-2M150 110 267 33" stroke="#eff0ce" strokeWidth="16" />
      <path d="M-8 40q62-20 130 8t151-10" stroke="#87b6ac" strokeWidth="9" fill="none" />
      <path d="m68 60 55-34 45 15-50 40Z" fill="#7ba766" stroke="#fff9df" strokeWidth="4" />
      <path d="M127 23c0 9-12 20-12 20s-12-11-12-20a12 12 0 1 1 24 0" fill="#21573f" />
      <circle cx="115" cy="23" r="4" fill="#fff9df" />
    </>
  ),
  crop: (
    <>
      <circle cx="199" cy="24" r="13" fill="#dfb963" />
      <path d="M0 64q59-40 134-11t126-14v61H0Z" fill="#c6d2a3" />
      <path d="M0 80q86-36 161-15t99-8v43H0Z" fill="#91ae79" />
      <path d="M0 83q95-19 175-4t85-5v26H0Z" fill="#786147" />
      {[77, 122, 167].map((x) => (
        <g key={x} transform={`translate(${x} 0)`}>
          <path d="M0 76V39" stroke="#355c3a" strokeWidth="3" />
          <path d="M0 61q-16 0-21-18Q-3 43 0 61M0 48q1-18 18-23Q17 42 0 48" fill="#47754c" />
          <path d="m0 77-4 11m4-11 6 8" stroke="#ddc5a2" fill="none" />
        </g>
      ))}
    </>
  ),
  report: (
    <>
      <path d="M0 91 106 35l154 39v26H0Z" fill="#c3d4ae" />
      <path d="m130 100 72-46 62 16v30Z" fill="#91b298" />
      <g transform="rotate(-7 123 50)">
        <rect x="83" y="11" width="82" height="80" rx="5" fill="#8ca18c" />
        <rect x="80" y="8" width="82" height="80" rx="5" fill="#fffdf1" stroke="#77927b" />
        <path d="M93 23h43m-43 8h27" stroke="#6e8470" strokeWidth="3" strokeLinecap="round" />
        <path d="M93 45h56v21H93Z" fill="#e3ecda" />
        <path d="m95 60 11-5 10 2 14-10 16 4" stroke="#47755c" strokeWidth="3" fill="none" />
        <path d="M93 76h32" stroke="#a6b89a" strokeWidth="3" strokeLinecap="round" />
      </g>
    </>
  ),
};

export default function StepIllustration({ scene }: { scene: keyof typeof scenes }) {
  return (
    <svg className="step-illustration" viewBox="0 0 260 96" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <rect width="260" height="96" fill="#e9eddb" />
      {scenes[scene]}
    </svg>
  );
}
