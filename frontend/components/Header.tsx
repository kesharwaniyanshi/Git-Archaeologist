export default function Header() {
  return (
    <header className="bg-gray-900/50 backdrop-blur-sm border-b border-gray-700">
      <div className="container mx-auto px-4 py-6">
        <div className="flex items-center gap-3">
          <div className="text-4xl">🔍</div>
          <div>
            <h1 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-primary-400 to-primary-600">
              Git Archaeologist
            </h1>
            <p className="text-gray-400 text-sm mt-1">
              Unearth the story behind your code changes
            </p>
          </div>
        </div>
      </div>
    </header>
  )
}
