export function contrastText(hex: string): '#1B1B1B' | '#FFFFFF' {
  const red = Number.parseInt(hex.slice(1, 3), 16)
  const green = Number.parseInt(hex.slice(3, 5), 16)
  const blue = Number.parseInt(hex.slice(5, 7), 16)
  return red * 299 + green * 587 + blue * 114 < 148_000 ? '#FFFFFF' : '#1B1B1B'
}

export function shortCode(code: string): string {
  return code.split('-').at(-1) || code
}
