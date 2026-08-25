import { Navigate, Route, Routes } from 'react-router-dom'
import ProtectedRoute from '../auth/ProtectedRoute'
import Dashboard from '../pages/Dashboard'
import GroupDetail from '../pages/GroupDetail'
import Login from '../pages/Login'
import Register from '../pages/Register'

export default function AppRoutes() { return <Routes><Route path="/login" element={<Login />} /><Route path="/register" element={<Register />} /><Route element={<ProtectedRoute />}><Route path="/dashboard" element={<Dashboard />} /><Route path="/groups/:groupId" element={<GroupDetail />} /></Route><Route path="*" element={<Navigate to="/dashboard" replace />} /></Routes> }
