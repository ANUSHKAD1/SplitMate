const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function validateLogin({ email, password }) {
  const errors = {}
  if (!email.trim()) errors.email = 'Email is required.'
  else if (!emailPattern.test(email.trim())) errors.email = 'Enter a valid email address.'
  if (!password) errors.password = 'Password is required.'
  return errors
}

export function validateRegistration({ name, email, password }) {
  const errors = validateLogin({ email, password })
  if (!name.trim()) errors.name = 'Name is required.'
  if (password && password.length < 8) errors.password = 'Password must be at least 8 characters.'
  else if (password && !/[A-Z]/.test(password)) errors.password = 'Password must include an uppercase letter.'
  else if (password && !/[a-z]/.test(password)) errors.password = 'Password must include a lowercase letter.'
  else if (password && !/\d/.test(password)) errors.password = 'Password must include a number.'
  else if (password && !/[^\w\s]/.test(password)) errors.password = 'Password must include a special character.'
  return errors
}
