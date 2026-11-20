import { NotebookDraftService } from './notebook-draft.service';

describe('NotebookDraftService code hand-off ("Ver el código")', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => localStorage.clear());

  it('queues code and hands it over exactly once', () => {
    const service = new NotebookDraftService();
    service.enqueue('df.head()');
    service.enqueue('df.describe()');
    expect(service.takeQueue()).toEqual(['df.head()', 'df.describe()']);
    expect(service.takeQueue()).toEqual([]);
  });

  it('falls back to memory when localStorage is blocked', () => {
    spyOn(Storage.prototype, 'setItem').and.throwError('blocked');
    spyOn(Storage.prototype, 'getItem').and.throwError('blocked');
    const service = new NotebookDraftService();
    service.enqueue('df.shape');
    expect(service.takeQueue()).toEqual(['df.shape']);
  });
});
