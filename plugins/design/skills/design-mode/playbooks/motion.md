# Motion

動きをつける・直す。

1. **要否と中身を決める。** **animate** の順番（動かすべきか → 目的 → 道具 → property → 曲線と長さ → 中断 → 退場）で決める。キーボード操作・頻繁に出る面・数値データは動かさない側に倒す
2. **複数の要素が動くなら** **choreograph** で順番・重なり・止めておくものを決める
3. **指で触る動きなら** **gestures** で 1:1 の追従と中断可能性を作る。iOS 的な物理感が要るなら **apple-design** も読む
4. **カクつくなら** **animation-performance** で composite のみの property に寄せ、main thread から外す
5. **見て確かめる。** 録画か複数フレームで見る。`prefers-reduced-motion` のときの挙動も確かめる
