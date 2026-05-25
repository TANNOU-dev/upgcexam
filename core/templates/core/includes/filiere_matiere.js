function initFiliereMatiereFilter(filiereSelectId, matiereSelectId, matieresParFiliere) {
    const filiereSelect = document.getElementById(filiereSelectId);
    const matiereSelect = document.getElementById(matiereSelectId);
    if (!filiereSelect || !matiereSelect) return;

    function remplirMatieres(filiereId, valeurSelectionnee) {
        matiereSelect.innerHTML = '<option value="">Sélectionner une matière</option>';
        const liste = matieresParFiliere[filiereId] || [];
        liste.forEach((m) => {
            const opt = document.createElement('option');
            opt.value = m.id;
            opt.textContent = m.nom;
            if (String(m.id) === String(valeurSelectionnee)) {
                opt.selected = true;
            }
            matiereSelect.appendChild(opt);
        });
        matiereSelect.disabled = liste.length === 0;
    }

    filiereSelect.addEventListener('change', () => {
        remplirMatieres(filiereSelect.value, '');
    });

    if (filiereSelect.value) {
        remplirMatieres(filiereSelect.value, matiereSelect.dataset.selected || '');
    } else {
        matiereSelect.disabled = true;
    }
}
