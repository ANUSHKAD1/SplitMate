// const rupeeFormatter = new Intl.NumberFormat('en-IN', {
//   style: 'currency',
//   currency: 'INR',
//   minimumFractionDigits: 2,
//   maximumFractionDigits: 2,
// })

// export function formatIndianRupees(amountInSmallestUnit) {
//   return rupeeFormatter.format(amountInSmallestUnit / 100)
// }
// const rupeeFormatter = new Intl.NumberFormat('en-IN', {
//   style: 'currency',
//   currency: 'INR',
//   minimumFractionDigits: 2,
//   maximumFractionDigits: 2,
// })

// export function formatIndianRupees(amount) {
//   const numericAmount = Number(amount)

//   if (!Number.isFinite(numericAmount)) {
//     return '₹0.00'
//   }

//   return rupeeFormatter.format(numericAmount)
// }
const rupeeFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export function formatIndianRupees(amount) {
  const numericAmount = Number(amount)

  if (!Number.isFinite(numericAmount)) {
    return '₹0.00'
  }

  return rupeeFormatter.format(numericAmount)
}