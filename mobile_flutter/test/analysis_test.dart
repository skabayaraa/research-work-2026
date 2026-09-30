import 'package:flutter_test/flutter_test.dart';
import 'package:agshilt_ai/analysis.dart';
import 'package:agshilt_ai/models.dart';

List<Contraction> seq(int n, double ivMin, double durS) => [
      for (var i = 0; i < n; i++)
        Contraction(start: i * ivMin * 60, end: i * ivMin * 60 + durS, pain: 6)
    ];

void main() {
  test('5 минут тутам, 60 с агшилт', () {
    final cs = seq(13, 5, 60);
    final s = computeStats(cs, cs.last.end);
    expect(s.meanInterval, closeTo(5.0, 1e-9));
    expect(s.meanDuration, closeTo(60.0, 1e-9));
  });
  test('5-1-1 нэг цаг тогтвортой бол HIGH', () {
    final cs = seq(16, 4.8, 65);
    expect(offlineRule(cs, 39, {}, cs.last.end), 'HIGH');
  });
  test('Улаан тугт шинж тэмдэг бол HIGH', () {
    expect(offlineRule(seq(2, 20, 30), 39, {'bleeding'}, 1300), 'HIGH');
  });
  test('10 с-ээс богино товшилтыг хасна', () {
    final out = clean([const Contraction(start: 0, end: 4), const Contraction(start: 100, end: 160)]);
    expect(out.length, 1);
  });
}
