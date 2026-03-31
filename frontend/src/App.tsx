import { AuthGuard } from "./components/AuthGuard"
import { BattleArena } from "./components/BattleArena"

export const App = () => {
  return (
    <AuthGuard>
      {({ userId, username, onLogout }) => (
        <BattleArena
          userId={userId}
          username={username}
          onLogout={onLogout}
        />
      )}
    </AuthGuard>
  )
}
