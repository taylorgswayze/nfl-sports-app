import { Routes, Route, Navigate } from 'react-router-dom'
import { BottomGutter } from './components/Almanac'
import GameDisplay from './components/GameDisplay'
import Standings from './components/Standings'
import TeamSchedule from './components/TeamSchedule'
import GameDetail from './components/GameDetail'
import PositionStats from './components/PositionStats'
import TeamStatComparison from './components/TeamStatComparison'
import DraftBoard from './components/DraftBoard'
import DraftAdvisor from './components/DraftAdvisor'
import MyLeagues from './components/MyLeagues'

function App() {
  return (
    <div className="page">
      <Routes>
        <Route path="/" element={<GameDisplay />} />
        <Route path="/standings" element={<Standings />} />
        <Route path="/game/:eventId" element={<GameDetail />} />
        <Route path="/team/:id" element={<TeamSchedule />} />
        <Route path="/position/:position/stats" element={<PositionStats />} />
        <Route path="/team-stat/:statName" element={<TeamStatComparison />} />
        <Route path="/draft" element={<DraftBoard />} />
        <Route path="/draft/advisor" element={<DraftAdvisor />} />
        <Route path="/leagues" element={<MyLeagues />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <BottomGutter />
    </div>
  )
}

export default App
