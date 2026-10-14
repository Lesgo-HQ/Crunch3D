export default function Navbar() {
  return (
    <nav className="site-navbar flex justify-center items-center w-full z-50" aria-label="Main navigation">
      <div className="flex items-center gap-6 px-6 py-3 bg-[#0A0A0A] rounded-[14px] text-[#F2F2F2]">
        <span className="font-semibold">Crunch3D · Local optimizer</span>
        <a href="https://github.com/Lesgo-HQ/Crunch3D" target="_blank" rel="noopener noreferrer">GitHub</a>
      </div>
    </nav>
  )
}
