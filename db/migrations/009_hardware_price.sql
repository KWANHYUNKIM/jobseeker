-- 009 — PC 부품과 일별 가격
--
-- 왜. 부품 가격은 매일 움직이고 지난날 가격은 다시 받을 수 없다 — 다나와의 가격 차트는
-- robots 가 막고 있어서(/info/ajax/) 우리가 매일 찍은 값이 곧 이력이다. 파일(prices.json)
-- 하나에만 두면 외주 단가 원장처럼 머신마다 따로 놀거나 덮어써져 사라진다.
--
-- hw_part      : 부품 목록. 원본은 hw-engine 이 고치는 public/hardware/parts.json 이고
--                여기는 크롤 때마다 그 사본을 맞춘다(등급은 저장하지 않는다 — 문턱에서 계산).
-- hw_price_day : 부품 × 날짜 한 줄. 같은 날 다시 돌면 마지막 값으로 바꾼다.
-- hw_offer_day : 그날 그 부품으로 잡힌 매물(가격 오름차순 몇 건). 상품명·가격·상품번호만 —
--                이미지·설명·스펙 문자열은 받지 않는다(crawl_hardware 머리말).
--
-- 적용:  psql "$JOBSEEKER_DSN" -f db/migrations/009_hardware_price.sql   (두 번 돌려도 안전)
-- schema.sql 의 "18. PC 부품 가격" 과 글자 그대로 같다.

BEGIN;

CREATE TABLE IF NOT EXISTS hw_part (
    id          text PRIMARY KEY,               -- 'gpu-rtx-5070-ti'
    category    text NOT NULL,
    name        text NOT NULL,
    maker       text,
    specs       jsonb NOT NULL DEFAULT '{}'::jsonb,
    perf_index  real,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT hw_part_category CHECK (category IN ('gpu','cpu','ram','ssd','hdd','mainboard','psu','cooler','case'))
);

CREATE TABLE IF NOT EXISTS hw_price_day (
    day           date    NOT NULL,
    part_id       text    NOT NULL REFERENCES hw_part(id) ON DELETE CASCADE,
    min_price     integer NOT NULL,
    median_price  integer NOT NULL,
    n             integer NOT NULL,
    source        text    NOT NULL DEFAULT 'danawa',
    PRIMARY KEY (day, part_id)
);
CREATE INDEX IF NOT EXISTS hw_price_day_part ON hw_price_day (part_id, day);

CREATE TABLE IF NOT EXISTS hw_offer_day (
    day      date    NOT NULL,
    part_id  text    NOT NULL REFERENCES hw_part(id) ON DELETE CASCADE,
    pcode    text    NOT NULL,
    name     text    NOT NULL,
    price    integer NOT NULL,
    PRIMARY KEY (day, part_id, pcode)
);

COMMIT;
