import { looksLikeMoney } from './money-format';

describe('looksLikeMoney (whole words, mirrors chart_builder._looks_like_money)', () => {
  it('no longer matches keywords hidden inside other words', () => {
    for (const name of ['Inventario', 'Clientes activa', 'Cuenta privada', 'Iniciativa', 'Tasa nominativa']) {
      expect(looksLikeMoney(name)).withContext(name).toBeFalse();
    }
  });

  it('matches whole words, plurals, separators and camelCase', () => {
    for (const name of ['Valor Total', 'Ventas', 'valor_neto', 'precio-unitario', 'totalVentas', 'Neto']) {
      expect(looksLikeMoney(name)).withContext(name).toBeTrue();
    }
  });

  it('keeps the space-split header and the "cantidad" override', () => {
    expect(looksLikeMoney('N E T O')).toBeTrue();
    expect(looksLikeMoney('Cantidad Venta')).toBeFalse();
  });
});
