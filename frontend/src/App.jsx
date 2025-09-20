import { Routes, Route, Navigate } from 'react-router-dom'
import GameDisplay from './components/GameDisplay'
import TeamSchedule from './components/TeamSchedule'
import PositionStats from './components/PositionStats'

function App() {
  return (
    <div id="app">
      <div className="container">
        <Routes>
          <Route path="/" element={<GameDisplay />} />
          <Route path="/team/:id" element={<TeamSchedule />} />
          <Route path="/position/:position/stats" element={<PositionStats />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </div>
  )
}

export default App
