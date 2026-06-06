import { describe, expect, it } from 'vitest';
import { COLORS } from './chartTheme';

describe('chartTheme', () => {
  it('uses a light consulting-style chart surface', () => {
    expect(COLORS.background).toBe('#ffffff');
    expect(COLORS.tooltipBg).toBe('#ffffff');
    expect(COLORS.grid).not.toBe('#1e293b');
  });

  it('keeps deep blue and teal as the primary accents', () => {
    expect(COLORS.product.slice(0, 2)).toEqual(['#1d4ed8', '#0f766e']);
  });
});
