import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { AuthProvider } from "./hooks/auth-provider"
import { AuthGuard } from "./components/AuthGuard"
import { AppLayout } from "./components/layout/AppLayout"
import { LoginPage } from "./pages/LoginPage"
import { RegisterPage } from "./pages/RegisterPage"
import { TrainingPage } from "./pages/TrainingPage"
import { BattlePage } from "./pages/BattlePage"
import { JoinPage } from "./pages/JoinPage"
import { UnrankedPage } from "./pages/UnrankedPage"
import {
  AboutPage,
  LeaderboardPage,
  NotFoundPage,
  RankedPage,
  SecurityPage,
  SuggestionsPage,
} from "./pages/InfoPages"

export const App = () => (
  <BrowserRouter>
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        <Route element={<AuthGuard />}>
          <Route element={<AppLayout />}>
            <Route path="/" element={<Navigate to="/training" replace />} />
            <Route path="/training" element={<TrainingPage />} />
            <Route path="/ranked" element={<RankedPage />} />
            <Route path="/unranked" element={<UnrankedPage />} />
            <Route path="/battle/:id" element={<BattlePage />} />
            <Route path="/join/:code" element={<JoinPage />} />
            <Route path="/suggestions" element={<SuggestionsPage />} />
            <Route path="/leaderboard" element={<LeaderboardPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/security" element={<SecurityPage />} />
          </Route>
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AuthProvider>
  </BrowserRouter>
)
