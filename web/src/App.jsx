import { useEffect } from 'react'
import DemoApp from './DemoApp'

export default function App() {
  useEffect(() => {
    document.body.setAttribute('data-view', 'demo')
    return () => document.body.removeAttribute('data-view')
  }, [])

  return <DemoApp />
}
