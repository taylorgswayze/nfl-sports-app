import { Routes, Route, Navigate } from 'react-router-dom'
import GameDisplay from './components/GameDisplay'
import TeamSchedule from './components/TeamSchedule'
import GameDetail from './components/GameDetail'
import PositionStats from './components/PositionStats'
import TeamStatComparison from './components/TeamStatComparison'

function App() {
  return (
    <div className="page">
      <Routes>
        <Route path="/" element={<GameDisplay />} />
        <Route path="/game/:eventId" element={<GameDetail />} />
        <Route path="/team/:id" element={<TeamSchedule />} />
        <Route path="/position/:position/stats" element={<PositionStats />} />
        <Route path="/team-stat/:statName" element={<TeamStatComparison />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  )
}

export default App
