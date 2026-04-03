-- ═══════════════════════════════════════════════════════════════
--  Seed all trusted sources used by both scrapers.
--  Run in Supabase → SQL Editor.
--  ON CONFLICT DO NOTHING (no column specified) silently skips
--  rows that violate ANY unique constraint on the table —
--  including both source_name AND official_url. Safe to re-run.
-- ═══════════════════════════════════════════════════════════════

INSERT INTO trusted_sources (source_name, official_url, category) VALUES
  ('Citi Newsroom',                        'https://citinewsroom.com',                                                           'Media'),
  ('Joy Online',                            'https://www.myjoyonline.com/news/',                                                  'Media'),
  ('Pulse Ghana',                           'https://www.pulse.com.gh/',                                                          'Media'),
  ('Graphic Online',                        'https://www.graphic.com.gh/news/general-news.html',                                  'Media'),
  ('Daily Graphic',                         'https://www.graphic.com.gh/',                                                        'Media'),
  ('GhanaWeb',                              'https://www.ghanaweb.com/',                                                          'Media'),
  ('Yen Ghana',                             'https://yen.com.gh/',                                                                'Media'),
  ('Ghana News Agency',                     'https://www.ghananewsagency.org/',                                                   'Media'),
  ('3News',                                 'https://3news.com/',                                                                 'Media'),
  ('Citinewsroom',                          'https://citinewsroom.com/category/news/',                                            'Media'),
  ('Peacefm Online',                        'https://www.peacefmonline.com/',                                                     'Media'),

  ('Office of the President',               'https://presidency.gov.gh/',                                                         'Government'),
  ('Ghana Government Portal',              'https://www.ghana.gov.gh/',                                                           'Government'),
  ('Parliament of Ghana',                   'https://www.parliament.gh/news',                                                     'Government'),

  ('Ministry of Finance',                   'https://mofep.gov.gh/',                                                              'Government'),
  ('Ministry of Foreign Affairs',           'https://mfa.gov.gh/',                                                                'Government'),
  ('Ministry of Health',                    'https://www.moh.gov.gh/',                                                            'Government'),
  ('Ministry of Communication',             'https://moc.gov.gh/',                                                                'Government'),
  ('Ministry of the Interior',              'https://www.mint.gov.gh/',                                                           'Government'),
  ('Ministry of Tourism',                   'https://www.touringghana.com/',                                                      'Government'),
  ('Ministry of Local Government',          'http://www.mlgrd.gov.gh/',                                                           'Government'),
  ('Ministry of Defence',                   'https://mod.gov.gh/',                                                                'Government'),
  ('Ministry of Education',                 'https://moe.gov.gh/',                                                                'Government'),
  ('Ministry of Energy',                    'https://www.energymin.gov.gh/',                                                      'Government'),
  ('Ministry of Roads and Highways',        'https://www.mrh.gov.gh/',                                                            'Government'),
  ('Ministry of Trade and Industry',        'http://www.moti.gov.gh/',                                                            'Government'),
  ('Ministry of Justice',                   'https://mojag.gov.gh/',                                                              'Government'),

  ('Judicial Service',                      'https://judicial.gov.gh/index.php/publications/news-publications/js-latest-news',    'Government'),
  ('Judicial Service of Ghana',             'https://www.judicial.gov.gh/',                                                       'Government'),

  ('Bank of Ghana',                         'https://www.bog.gov.gh/all-news-page/',                                              'Finance'),
  ('Securities and Exchange Comm',          'https://sec.gov.gh/',                                                                'Finance'),
  ('National Insurance Commission',         'https://nicghana.org/',                                                              'Finance'),
  ('NPRA',                                  'https://www.npra.gov.gh/',                                                           'Finance'),
  ('CAGD',                                  'https://cagd.gov.gh/',                                                               'Finance'),
  ('Ghana Revenue Authority',               'https://gra.gov.gh/',                                                                'Finance'),

  ('Communication Authority',               'https://nca.org.gh/',                                                                'Regulatory'),
  ('National Communications Auth',          'https://www.nca.org.gh/',                                                            'Regulatory'),
  ('National Identification Authority',     'https://nia.gov.gh/',                                                                'Regulatory'),
  ('Electoral Commission',                  'https://www.ec.gov.gh/',                                                             'Regulatory'),
  ('National Development Planning',         'https://www.ndpc.gov.gh/',                                                           'Regulatory'),
  ('Public Procurement Authority',          'https://www.ppbghana.org/',                                                          'Regulatory'),
  ('Public Utilities Regulatory',           'http://www.purc.com.gh/',                                                            'Regulatory'),
  ('Ghana Standards Authority',             'https://www.gsa.gov.gh/',                                                            'Regulatory'),
  ('Food and Drugs Authority',              'https://www.fdaghana.gov.gh/',                                                       'Regulatory'),
  ('Data Protection Commission',            'https://dataprotection.gov.gh/',                                                     'Regulatory'),
  ('Cyber Security Authority',              'https://www.csa.gov.gh/',                                                            'Regulatory'),
  ('NITA',                                  'https://nita.gov.gh/',                                                               'Regulatory'),
  ('National Commission on Culture',        'http://www.ghanaculture.gov.gh/',                                                    'Regulatory'),

  ('Ghana Health Service',                  'https://ghs.gov.gh/',                                                                'Health'),
  ('National Health Insurance Auth',        'https://www.nhis.gov.gh/',                                                           'Health'),
  ('SSNIT',                                 'https://www.ssnit.org.gh/',                                                          'Health'),

  ('Volta River Authority (VRA)',            'https://www.vra.com/',                                                               'Energy'),
  ('Volta River Authority News',            'https://www.vra.com/media/2022_news.php',                                            'Energy'),
  ('Energy Commission',                     'https://www.energycom.gov.gh/index.php/media-center/latest-news',                   'Energy'),
  ('GRIDCo',                                'https://www.gridcogh.com/',                                                          'Energy'),

  ('GIMPA',                                 'https://www.gimpa.edu.gh/',                                                          'Education'),
  ('Ghana Education Service',               'https://ges.gov.gh/',                                                                'Education'),
  ('National Teaching Council',             'https://ntc.gov.gh/',                                                                'Education'),
  ('National Accreditation Board',          'https://nab.gov.gh/',                                                                'Education'),
  ('CSIR',                                  'http://www.csir.org.gh/',                                                            'Education'),

  ('Ghana Statistical Service',             'https://www.statsghana.gov.gh/',                                                     'Government'),

  ('Ghana Investment Promotion Centre (GIPC)', 'https://gipc.gov.gh/news-articles/',                                             'Government'),
  ('Ghana Investment Promotion',            'https://www.gipcghana.com/',                                                         'Government'),
  ('Ghana Export Promotion Auth',           'https://www.gepaghana.org/',                                                         'Government'),
  ('Ghana Free Zones Board',                'https://gfzb.gov.gh/',                                                               'Government'),
  ('Association of Ghana Industries',       'https://www.agighana.org/',                                                          'Industry'),
  ('Private Enterprise Federation',         'https://pef.org.gh/',                                                                'Industry'),

  ('Ghana Tourism Authority',               'https://ghana.travel/blog/',                                                         'Government'),

  ('Ghana Armed Forces',                    'https://gafonline.mil.gh/',                                                          'Government'),
  ('Ghana Police Service',                  'https://www.police.gov.gh/',                                                         'Government'),
  ('DVLA',                                  'https://dvla.gov.gh/',                                                               'Government'),

  ('Local Government Service',              'https://lgs.gov.gh/',                                                                'Government')
ON CONFLICT DO NOTHING;
