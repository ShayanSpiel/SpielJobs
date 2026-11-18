export function SocialIcon({ name }: { name: 'linkedin' | 'github' | 'x' }) {
  if (name === 'x') {
    return (
      <svg className="social-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.64 7.584H.47l8.6-9.835L0 1.154h7.594l5.243 6.932 6.064-6.933Zm-1.29 19.49h2.04L6.488 3.24H4.3l13.31 17.403Z" />
      </svg>
    )
  }
  return <i className={`bx bxl-${name}`} aria-hidden="true" />
}
