-- =============================================================================
-- ChronoLegal — Sample Legal Cases Seed Data
-- Landmark Indian Supreme Court judgments for development/testing
-- =============================================================================

INSERT INTO legal_cases (
    id, case_id, case_name, case_number, petitioner, respondent,
    court, judges, judgment_date, acts, sections, keywords,
    full_text, summary, decision_type, text_length, is_embedded, chunk_count,
    created_at, updated_at
) VALUES

(
    gen_random_uuid(),
    'kesavananda-bharati-1973',
    'Kesavananda Bharati v. State of Kerala',
    'W.P. (C) No. 135/1970',
    'Kesavananda Bharati',
    'State of Kerala',
    'Supreme Court of India',
    ARRAY['Y.V. Chandrachud', 'H.R. Khanna', 'K.S. Hegde', 'A.N. Grover', 'P. Jaganmohan Reddy',
          'D.G. Palekar', 'H.M. Beg', 'A.K. Mukherjea', 'B.K. Mukherjea', 'S.N. Dwivedi',
          'A.N. Ray', 'K.K. Mathew', 'M.H. Beg'],
    '1973-04-24',
    ARRAY['Constitution of India', 'Kerala Land Reforms Act 1963'],
    ARRAY['Article 13', 'Article 368', 'Article 32'],
    ARRAY['basic structure', 'constitutional amendment', 'fundamental rights', 'Parliament', 'judicial review'],
    'The Supreme Court of India in this landmark case, by a majority of 7:6, propounded the doctrine of basic structure of the Constitution. The Court held that while Parliament has wide powers to amend the Constitution under Article 368, it cannot destroy, damage or emasculate the basic structure or essential features of the Constitution. The basic features include supremacy of the Constitution, republican and democratic form of government, secular character, separation of powers, federalism, and fundamental rights. This judgment overruled the earlier Golak Nath case and held that Parliament could amend fundamental rights but subject to the basic structure limitation. The case arose when Kesavananda Bharati, the head of a religious denomination, challenged the Kerala Land Reforms Act which imposed restrictions on the management of religious property.',
    'Landmark judgment establishing the Basic Structure Doctrine. Parliament cannot amend the Constitution to destroy its essential features. Fundamental rights can be amended but the basic structure must be preserved.',
    'Partly Allowed',
    8500,
    FALSE, 0,
    NOW(), NOW()
),

(
    gen_random_uuid(),
    'maneka-gandhi-1978',
    'Maneka Gandhi v. Union of India',
    'W.P. No. 231/1977',
    'Maneka Gandhi',
    'Union of India',
    'Supreme Court of India',
    ARRAY['M.H. Beg', 'Y.V. Chandrachud', 'V.R. Krishna Iyer', 'P.N. Bhagwati', 'N.L. Untwalia', 'S. Murtaza Fazl Ali', 'P.S. Kailasam'],
    '1978-01-25',
    ARRAY['Constitution of India', 'Passports Act 1967'],
    ARRAY['Article 14', 'Article 19', 'Article 21'],
    ARRAY['personal liberty', 'due process', 'natural justice', 'passport', 'freedom of movement'],
    'The Supreme Court in this landmark judgment expanded the scope of Article 21 of the Constitution, which guarantees the right to life and personal liberty. The petitioner''s passport was impounded by the Government without giving her any reason or opportunity to be heard. The Court held that the procedure prescribed by law for depriving a person of life or personal liberty must be fair, just, and reasonable. It must satisfy the requirements of Articles 14 and 19 as well. This judgment connected the three golden triangle of Articles 14, 19, and 21 and held that these articles are not mutually exclusive but supplement each other. The right to travel abroad was held to be part of personal liberty under Article 21.',
    'Expanded Article 21 to include due process. The procedure for depriving personal liberty must be fair, just and reasonable. Articles 14, 19 and 21 are interconnected — the Golden Triangle.',
    'Allowed',
    6200,
    FALSE, 0,
    NOW(), NOW()
),

(
    gen_random_uuid(),
    'olga-tellis-1985',
    'Olga Tellis v. Bombay Municipal Corporation',
    'W.P. No. 4930/1985',
    'Olga Tellis',
    'Bombay Municipal Corporation',
    'Supreme Court of India',
    ARRAY['Y.V. Chandrachud', 'D.A. Desai', 'O. Chinnappa Reddy', 'E.S. Venkataramiah', 'Ranganath Misra'],
    '1985-07-10',
    ARRAY['Constitution of India', 'Bombay Municipal Corporation Act 1888'],
    ARRAY['Article 21', 'Article 19(1)(e)'],
    ARRAY['right to livelihood', 'pavement dwellers', 'eviction', 'slums', 'life'],
    'The Supreme Court held that the right to livelihood is an integral component of the right to life guaranteed under Article 21 of the Constitution. The case involved pavement dwellers and slum dwellers in Bombay who challenged their eviction by the Municipal Corporation. The Court held that no person can live without means of living, and the right to life under Article 21 includes the right to livelihood. However, the Court also recognized the right of the state to remove encroachments, but directed that alternative accommodation should be provided. The judgment expanded the horizons of Article 21 to include socio-economic rights.',
    'Right to livelihood is part of right to life under Article 21. The State must provide alternative accommodation before evicting pavement dwellers.',
    'Partly Allowed',
    5800,
    FALSE, 0,
    NOW(), NOW()
),

(
    gen_random_uuid(),
    'vishaka-1997',
    'Vishaka v. State of Rajasthan',
    'W.P. (Crl.) No. 666/1992',
    'Vishaka and Others',
    'State of Rajasthan and Others',
    'Supreme Court of India',
    ARRAY['J.S. Verma', 'Sujata V. Manohar', 'B.N. Kirpal'],
    '1997-08-13',
    ARRAY['Constitution of India', 'International Convention on Elimination of All Forms of Discrimination Against Women'],
    ARRAY['Article 14', 'Article 15', 'Article 19', 'Article 21'],
    ARRAY['sexual harassment', 'workplace', 'women', 'gender equality', 'fundamental rights'],
    'The Supreme Court issued guidelines to prevent sexual harassment of women at workplaces. The case arose after the gang rape of a social worker in Rajasthan who was trying to prevent a child marriage. In the absence of domestic legislation on workplace sexual harassment, the Court drew upon international conventions and the constitutional provisions to lay down Vishaka Guidelines. These guidelines defined sexual harassment and required employers to set up Complaints Committees. The judgment remained the law until Parliament enacted the Sexual Harassment of Women at Workplace (Prevention, Prohibition and Redressal) Act, 2013.',
    'Landmark case laying down Vishaka Guidelines on prevention of sexual harassment at workplaces. Court exercised its power under Article 32 in absence of legislation to fill the void.',
    'Guidelines Issued',
    4500,
    FALSE, 0,
    NOW(), NOW()
),

(
    gen_random_uuid(),
    'navtej-singh-johar-2018',
    'Navtej Singh Johar v. Union of India',
    'W.P. (Crl.) No. 76/2016',
    'Navtej Singh Johar',
    'Union of India',
    'Supreme Court of India',
    ARRAY['Dipak Misra', 'A.M. Khanwilkar', 'R.F. Nariman', 'D.Y. Chandrachud', 'Indu Malhotra'],
    '2018-09-06',
    ARRAY['Indian Penal Code 1860', 'Constitution of India'],
    ARRAY['Section 377', 'Article 14', 'Article 15', 'Article 19', 'Article 21'],
    ARRAY['LGBT rights', 'Section 377', 'decriminalization', 'sexual orientation', 'dignity'],
    'The Supreme Court in a unanimous verdict decriminalized consensual same-sex relations between adults by reading down Section 377 of the Indian Penal Code. The Court held that Section 377, to the extent it criminalized consensual sexual acts between adults of the same sex in private, was unconstitutional as it violated Articles 14, 15, 19, and 21 of the Constitution. The judgment recognized sexual orientation as an innate and integral component of identity and held that members of the LGBT community are entitled to equal citizenship. The Court overruled its own earlier judgment in Suresh Kumar Koushal v. Naz Foundation (2013) which had restored Section 377.',
    'Unanimous verdict decriminalizing consensual same-sex relations. Section 377 IPC, insofar as it criminalizes adult consensual acts, held unconstitutional. LGBT persons entitled to full constitutional protection.',
    'Allowed',
    9200,
    FALSE, 0,
    NOW(), NOW()
),

(
    gen_random_uuid(),
    'sr-bommai-1994',
    'S.R. Bommai v. Union of India',
    'W.P. No. 235/1990',
    'S.R. Bommai',
    'Union of India',
    'Supreme Court of India',
    ARRAY['P.B. Sawant', 'Kuldip Singh', 'S.R. Pandian', 'A.M. Ahmadi', 'J.S. Verma', 'K. Ramaswamy', 'Yogeshwar Dayal', 'B.P. Jeevan Reddy', 'S.C. Agrawal'],
    '1994-03-11',
    ARRAY['Constitution of India'],
    ARRAY['Article 356', 'Article 74', 'Article 164'],
    ARRAY['President''s Rule', 'federalism', 'state government', 'floor test', 'secularism'],
    'The Supreme Court in this landmark judgment laid down detailed guidelines on the use and misuse of Article 356 of the Constitution which empowers the President to impose President''s Rule in a state. The Court held that the imposition of President''s Rule is subject to judicial review. It also held that before imposing President''s Rule, the government must give an opportunity to the state government to prove its majority on the floor of the House. The judgment strengthened federalism in India and held that secularism is a basic feature of the Constitution.',
    'Landmark judgment on Article 356 and President''s Rule. Floor test must precede dismissal of state government. Secularism is a basic feature of the Constitution. Laid down principles curbing misuse of Article 356.',
    'Allowed',
    7600,
    FALSE, 0,
    NOW(), NOW()
);
