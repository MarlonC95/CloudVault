const DATOS = [
  { valor: '15 GB', descripcion: 'gratis al registrarte' },
  { valor: '30 días', descripcion: 'para recuperar lo que borras' },
  { valor: '4 roles', descripcion: 'para trabajar en equipo' },
  { valor: '1 TB', descripcion: 'en el plan Empresarial' },
]

function FranjaDatos() {
  return (
    <section className="lp-datos" aria-label="CloudVault en números">
      <div className="lp-contenedor">
        <div className="row g-3">
          {DATOS.map((dato) => (
            <div key={dato.valor} className="col-6 col-lg-3">
              <div className="lp-dato">
                <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.02em', color: '#2563EB' }}>{dato.valor}</div>
                <div style={{ fontSize: 14, color: '#64748B' }}>{dato.descripcion}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export default FranjaDatos