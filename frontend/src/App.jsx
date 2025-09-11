import { useState } from 'react'
import { Routes, Route, Navigate, useParams } from 'react-router-dom'
import GameDisplay from './components/GameDisplay'
import TeamSchedule from './components/TeamSchedule'
import PositionStats from './components/PositionStats'

function TeamScheduleWrapper() {
  const { id } = useParams()
  return <TeamSchedule teamId={id} />
}

function PositionStatsWrapper() {
  const { position } = useParams()
  return <PositionStats position={position} />
}

function App() {
  const [currentView, setCurrentView] = useState("games")
  const [teamId, setTeamId] = useState(null)

  const showTeamSchedule = (selectedTeamId) => {
    setTeamId(selectedTeamId)
    setCurrentView("team")
  }

  const backToGameDisplay = () => {
    setCurrentView("games")
    setTeamId(null)
  }

  return (
    <div id="app">
      <div className="container">
        <Routes>
          <Route path="/" element={
            currentView === "games" ? 
              <GameDisplay onTeamSelect={showTeamSchedule} /> :
              <TeamSchedule teamId={teamId} onBack={backToGameDisplay} />
          } />
          <Route path="/team/:id" element={<TeamScheduleWrapper />} />
          <Route path="/position/:position/stats" element={<PositionStatsWrapper />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </div>
  )
}

export default App
