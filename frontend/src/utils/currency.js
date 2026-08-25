const rupeeFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export function formatIndianRupees(amountInSmallestUnit) {
  return rupeeFormatter.format(amountInSmallestUnit / 100)
}
